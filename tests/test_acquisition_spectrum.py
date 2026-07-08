"""
Tests for acquisition/spectrum_acquisition across the 3 scope dialects.

These tests assert that each dialect sends the same SCPI command
sequence as the legacy ``old/daq_gui_func.start_spectrum`` function
(see ``old/dictionary_SCPI.py`` for the source-of-truth command
strings).
"""

from __future__ import annotations

import unittest

from acquisition import scpi_dictionary as ds
from acquisition.spectrum_acquisition import (
    SCOPE_KEY,
    SCOPE_RTA,
    SCOPE_RTO,
    SpectrumAcquisition,
)
from tests.fake_connection import FakeConnection


class SpectrumRtaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = FakeConnection()
        # Each iteration: RTA reads two cursor Y positions, p1=2.0 and
        # p2=1.0 -> r_r=1.0. ``*OPC?`` (ds.rdy) is queried twice per
        # sample and must return a truthy response so the cursor
        # queries actually fire.
        self.conn.set_response(ds.rdy, "1")
        self.conn.set_response(ds.posC1, "2.0")
        self.conn.set_response(ds.posC2, "1.0")

    def test_rta_dialect_p1_minus_p2(self):
        acq = SpectrumAcquisition(scope_id=SCOPE_RTA, channel="MA1", num_datos=3)
        acq.set_connection(self.conn)
        result = acq.run()
        self.assertEqual(list(result.data), [1.0, 1.0, 1.0])
        # RTA should write FORM BIN and select the cursor source.
        self.assertIn("FORM BIN", self.conn.writes)
        self.assertIn(ds.selectChanCur("MA1"), self.conn.writes)
        # Two cursor queries per sample.
        self.assertEqual(self.conn.queries.count(ds.posC1), 3)
        self.assertEqual(self.conn.queries.count(ds.posC2), 3)
        # ``*OPC?`` is queried twice per sample (gates each cursor read).
        self.assertEqual(self.conn.queries.count(ds.rdy), 6)


class SpectrumRtoTests(unittest.TestCase):
    def test_rto_dialect_single_query(self):
        fake = FakeConnection()
        fake.set_response("MEAS1:RES:ACT? ", "0.42")
        acq = SpectrumAcquisition(scope_id=SCOPE_RTO, channel="MA1", num_datos=5)
        acq.set_connection(fake)
        result = acq.run()
        self.assertEqual(list(result.data), [0.42] * 5)
        self.assertIn("FORM BIN", fake.writes)
        self.assertIn(ds.selectChanCur("MA1"), fake.writes)
        self.assertEqual(fake.queries.count("MEAS1:RES:ACT? "), 5)


class SpectrumKeyTests(unittest.TestCase):
    def test_key_dialect(self):
        fake = FakeConnection()
        fake.set_response(ds.resultKey, "-0.13")
        acq = SpectrumAcquisition(scope_id=SCOPE_KEY, channel="MA2", num_datos=2)
        acq.set_connection(fake)
        result = acq.run()
        self.assertEqual(list(result.data), [-0.13, -0.13])
        self.assertIn(ds.headerOff, fake.writes)
        self.assertIn(ds.currmeasKey, fake.writes)
        self.assertEqual(fake.queries.count(ds.resultKey), 2)


class SpectrumProgressCallbackTests(unittest.TestCase):
    def test_callback_fires_every_100_samples(self):
        fake = FakeConnection()
        fake.set_response("MEAS1:RES:ACT? ", "0.5")
        acq = SpectrumAcquisition(scope_id=SCOPE_RTO, num_datos=250)
        acq.set_connection(fake)
        calls = []

        def cb(arr):
            calls.append(len(arr))

        acq.run(progress_callback=cb)
        # 100, 200 -> 2 callbacks
        self.assertEqual(calls, [100, 200])


class SpectrumCooperativeStopTests(unittest.TestCase):
    """The worker must respect request_stop() and exit between samples."""

    def test_request_stop_short_circuits_run(self):
        from acquisition.spectrum_acquisition import SpectrumAcquisition, SCOPE_RTA
        # We can't use threading.Timer here: the worker is fully
        # synchronous, so a timer fired from another thread would
        # race the (very fast) fake connection. Instead, the query
        # handler itself triggers the stop after a few calls, which
        # is exactly what would happen in a long-running scope query
        # when the user clicks Stop.
        acq_ref = {}
        call_counter = {"n": 0}

        def handler(cmd):
            call_counter["n"] += 1
            if call_counter["n"] >= 4:  # 2 cursor queries per sample, stop after 2 samples
                acq_ref["acq"].request_stop()
            if cmd == ds.posC1:
                return "2.0"
            if cmd == ds.posC2:
                return "1.0"
            return "1"  # *OPC?

        fake = _ScriptedConnection(handler)
        acq = SpectrumAcquisition(scope_id=SCOPE_RTA, channel="MA1", num_datos=1000)
        acq.set_connection(fake)
        acq_ref["acq"] = acq
        result = acq.run()
        self.assertLess(result.data.size, 1000)
        self.assertGreaterEqual(result.data.size, 1)
        for v in result.data:
            self.assertAlmostEqual(v, 1.0, places=6)

    def test_run_completes_normally_without_stop(self):
        from acquisition.spectrum_acquisition import SpectrumAcquisition, SCOPE_RTA
        fake = _ScriptedConnection(
            lambda cmd: "2.0" if cmd == ds.posC1 else ("1.0" if cmd == ds.posC2 else "1")
        )
        acq = SpectrumAcquisition(scope_id=SCOPE_RTA, channel="MA1", num_datos=5)
        acq.set_connection(fake)
        result = acq.run()
        self.assertEqual(result.data.size, 5)
        for v in result.data:
            self.assertAlmostEqual(v, 1.0, places=6)

    def test_per_query_timeout_is_applied(self):
        """The adapter must push a 5000ms per-query timeout down to
        the connection before each query, regardless of what the
        connection claims its own timeout is."""
        from acquisition.spectrum_acquisition import SpectrumAcquisition, SCOPE_RTA

        class TimeoutSpy(_ScriptedConnection):
            """A scripted connection that records every timeout it
            receives and remembers the latest one, so the adapter
            can read it back via getattr(conn, 'timeout')."""

            def __init__(self, handler):
                super().__init__(handler)
                self.timeouts_seen = []
                self._current_timeout = 20000

            def __setattr__(self, name, value):
                if name == "timeout":
                    self.timeouts_seen.append(value)
                    object.__setattr__(self, "_current_timeout", value)
                    return
                super().__setattr__(name, value)

            @property
            def timeout(self):
                return self._current_timeout

        fake = TimeoutSpy(
            lambda cmd: "2.0" if cmd == ds.posC1 else ("1.0" if cmd == ds.posC2 else "1")
        )
        acq = SpectrumAcquisition(scope_id=SCOPE_RTA, channel="MA1", num_datos=2)
        acq.set_connection(fake)
        acq.run()
        # Run-level timeout at start, then per-query timeouts.
        self.assertEqual(fake.timeouts_seen[0], 20000)
        # Each sample issues two cursor queries, so two 5000ms.
        self.assertIn(5000, fake.timeouts_seen)
        self.assertGreaterEqual(fake.timeouts_seen.count(5000), 2)
        # The final state must be the run-level timeout restored,
        # not a leftover 5000 from the last query.
        self.assertEqual(fake.timeouts_seen[-1], 20000)


class _ScriptedConnection:
    """Minimal scripted connection for tests that need a callback handler."""

    def __init__(self, handler):
        self.handler = handler
        self.writes: list = []
        self.queries: list = []
        self.closed = False

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.handler(command)

    def read_raw(self) -> bytes:
        return b""

    def close(self) -> None:
        self.closed = True

    @property
    def timeout(self):
        return None

    @timeout.setter
    def timeout(self, value):
        pass

    def __delattr__(self, name):
        if name == "timeout":
            return
        super().__delattr__(name)


if __name__ == "__main__":
    unittest.main()
