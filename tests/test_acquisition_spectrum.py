"""
Tests for acquisition/spectrum_acquisition across the 3 scope dialects.
"""

from __future__ import annotations

import unittest

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
        # Each iteration: RTA reads two values, p1=2.0 and p2=1.0 -> r_r=1.0
        # We alternate the responses so the test sees the right sequence.
        # Use prefix matching for ":MEAS:RES:ACT? P1" and "P2".
        self.p1_calls = 0
        self.p2_calls = 0

    def _query_handler(self, command: str) -> str:
        if ":MEAS:RES:ACT?" in command and "P1" in command:
            self.p1_calls += 1
            return "2.0"
        if ":MEAS:RES:ACT?" in command and "P2" in command:
            self.p2_calls += 1
            return "1.0"
        return ""

    def test_rta_dialect_p1_minus_p2(self):
        # Replace the default with a custom query that tracks the calls.
        fake = _ScriptedConnection(self._query_handler)
        acq = SpectrumAcquisition(scope_id=SCOPE_RTA, channel="MA1", num_datos=3)
        acq.set_connection(fake)
        result = acq.run()
        self.assertEqual(list(result.data), [1.0, 1.0, 1.0])
        # RTA should write FORM BIN and select channel once
        self.assertIn("FORM BIN", fake.writes)
        self.assertIn(":MEAS:RES:ACT MA1", fake.writes)
        self.assertEqual(self.p1_calls, 3)
        self.assertEqual(self.p2_calls, 3)


class SpectrumRtoTests(unittest.TestCase):
    def test_rto_dialect_single_query(self):
        fake = FakeConnection()
        fake.set_response("MEAS1:RES:ACT?", "0.42")
        acq = SpectrumAcquisition(scope_id=SCOPE_RTO, channel="MA1", num_datos=5)
        acq.set_connection(fake)
        result = acq.run()
        self.assertEqual(list(result.data), [0.42] * 5)
        self.assertIn("FORM BIN", fake.writes)
        self.assertIn(":MEAS:RES:ACT MA1", fake.writes)
        self.assertEqual(fake.queries.count("MEAS1:RES:ACT?"), 5)


class SpectrumKeyTests(unittest.TestCase):
    def test_key_dialect(self):
        fake = FakeConnection()
        fake.set_response(":MEAS:RES?", "-0.13")
        acq = SpectrumAcquisition(scope_id=SCOPE_KEY, channel="MA2", num_datos=2)
        acq.set_connection(fake)
        result = acq.run()
        self.assertEqual(list(result.data), [-0.13, -0.13])
        self.assertIn("FORM ASC", fake.writes)
        self.assertIn(":MEAS:RES MA2", fake.writes)
        self.assertEqual(fake.queries.count(":MEAS:RES?"), 2)


class SpectrumProgressCallbackTests(unittest.TestCase):
    def test_callback_fires_every_100_samples(self):
        fake = FakeConnection()
        fake.set_response("MEAS1:RES:ACT?", "0.5")
        acq = SpectrumAcquisition(scope_id=SCOPE_RTO, num_datos=250)
        acq.set_connection(fake)
        calls = []

        def cb(arr):
            calls.append(len(arr))

        acq.run(progress_callback=cb)
        # 100, 200 -> 2 callbacks
        self.assertEqual(calls, [100, 200])


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
