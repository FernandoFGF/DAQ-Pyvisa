"""
Tests for acquisition/iv_acquisition.

The adapter must reproduce the SCPI command sequence of
``old/daq_gui_func.start_iv`` (lines 51-90) so a Keithley
2470 connected to the same IP the user used with the legacy
build produces the same curve.
"""

from __future__ import annotations

import os
import unittest

from acquisition import scpi_dictionary as ds
from acquisition.iv_acquisition import IVAcquisition
from tests.fake_connection import FakeConnection


class IVAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = FakeConnection()
        # ``*OPC?`` returns '1' so the wait loop exits immediately.
        self.conn.set_response("*OPC?", "1")
        # ``:FETC:ARR:CURR? (@1)`` and ``:FETC:ARR:VOLT? (@1)`` return
        # comma-separated samples. Tests override per-case.
        self.conn.set_default_response("")

    def test_run_uses_correct_scpi_sequence(self):
        self.conn.set_response(ds.queryCurr, "0.1,0.2,0.3")
        self.conn.set_response(ds.queryVolt, "1.0,0.5,0.0")
        acq = IVAcquisition("smu", v_start=1.0, v_stop=0.0, v_step=0.5)
        acq.set_connection(self.conn)
        result = acq.run()
        self.assertEqual(len(result.voltage), 3)
        self.assertEqual(len(result.current), 3)
        self.assertEqual(result.points, 2)

        # The SCPI sequence is locked to match the legacy code
        # line by line, using the tokens from scpi_dictionary
        # (which is the modern home of the old dictionary_SCPI).
        self.assertEqual(self.conn.writes[0], ds.rst)
        # ds.voltMode = ":SOUR:VOLT:MODE VOLT"
        self.assertIn(ds.voltMode, self.conn.writes)
        # ds.sweepMode = ":SOUR:VOLT:MODE SWE"
        self.assertIn(ds.sweepMode, self.conn.writes)
        self.assertIn(ds.sweepSing, self.conn.writes)
        self.assertIn(ds.sweepLin, self.conn.writes)
        self.assertIn(":SOUR:VOLT:STAR 1.0", self.conn.writes)
        self.assertIn(":SOUR:VOLT:STOP 0.0", self.conn.writes)
        self.assertIn(":SOUR:VOLT:POIN 2", self.conn.writes)
        # Auto-range current measurement, NPLC 0.1, 10 mA prot.
        self.assertIn(ds.smuAuto1, self.conn.writes)
        self.assertIn(ds.smuAuto2, self.conn.writes)
        self.assertIn(ds.smuAuto3, self.conn.writes)
        # Trigger source = arm-and-trigger by sequencer.
        self.assertIn(ds.smuTrig, self.conn.writes)
        self.assertIn(":trig:coun 2", self.conn.writes)
        # Output on / init / off
        self.assertIn(ds.smuOn, self.conn.writes)
        # ds.smuInit = ":init (@1)" - the channel selector is
        # critical on the 2470.
        self.assertIn(ds.smuInit, self.conn.writes)
        self.assertIn(ds.smuOff, self.conn.writes)
        # ds.queryCurr = ":fetc:arr:curr? (@1)"
        self.assertEqual(self.conn.queries.count(ds.queryCurr), 1)
        # ds.queryVolt = ":fetc:arr:volt? (@1)"
        self.assertEqual(self.conn.queries.count(ds.queryVolt), 1)
        # *OPC? polled at least once in the wait loop.
        self.assertGreaterEqual(self.conn.queries.count("*OPC?"), 1)

    def test_query_includes_channel_selector(self):
        """The 2470 needs the (@1) channel specifier on
        :FETC:ARR:CURR? / :FETC:ARR:VOLT?; without it the SMU
        returns a single value and the array is broken. The
        legacy code always included (@1) and we do too."""
        self.conn.set_response(ds.queryCurr, "0.1")
        self.conn.set_response(ds.queryVolt, "0.0")
        acq = IVAcquisition("smu", v_start=0.0, v_stop=0.0, v_step=0.1)
        acq.set_connection(self.conn)
        acq.run()
        self.assertIn(ds.queryCurr, self.conn.queries)
        self.assertIn(ds.queryVolt, self.conn.queries)
        # The exact command sent must include (@1), not a bare query.
        self.assertTrue(ds.queryCurr.endswith("(@1)"),
                        f"FETC:CURR missing channel: {ds.queryCurr!r}")
        self.assertTrue(ds.queryVolt.endswith("(@1)"),
                        f"FETC:VOLT missing channel: {ds.queryVolt!r}")

    def test_run_returns_parsed_arrays(self):
        self.conn.set_response(ds.queryCurr, "1e-6,2e-6,3e-6,4e-6")
        self.conn.set_response(ds.queryVolt, "1.0,0.5,0.0,-0.5")
        acq = IVAcquisition("smu", v_start=1.0, v_stop=-0.5, v_step=0.5)
        acq.set_connection(self.conn)
        result = acq.run()
        self.assertEqual(list(result.voltage), [1.0, 0.5, 0.0, -0.5])
        self.assertEqual(list(result.current), [1e-6, 2e-6, 3e-6, 4e-6])

    def test_mismatched_array_lengths_are_padded(self):
        """Transient comms error: the SMU returns 3 currents but
        4 voltages (or vice versa). The legacy code would have
        raised ValueError when constructing the numpy array; we
        pad with NaN so the GUI still gets a valid (if sparser)
        IVResult and the plot does not crash."""
        self.conn.set_response(ds.queryCurr, "1e-6,2e-6,3e-6")
        self.conn.set_response(ds.queryVolt, "1.0,0.5,0.0,-0.5")
        acq = IVAcquisition("smu", v_start=1.0, v_stop=-0.5, v_step=0.5)
        acq.set_connection(self.conn)
        result = acq.run()
        self.assertEqual(len(result.voltage), 4)
        self.assertEqual(len(result.current), 4)
        # The current array was padded with NaN at index 3; the
        # voltage array was already 4 elements long.
        import math
        self.assertFalse(math.isnan(result.voltage[3]))
        self.assertEqual(result.voltage[3], -0.5)
        self.assertTrue(math.isnan(result.current[3]))
        self.assertEqual(result.voltage[0], 1.0)
        self.assertEqual(result.current[0], 1e-6)

    def test_save_writes_two_line_file(self):
        acq = IVAcquisition("smu")
        with __import__("tempfile").TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "iv.txt")
            acq.save(out, [1.0, 0.5, 0.0], [1e-6, 2e-6, 3e-6])
            with open(out, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0], "1.0 0.5 0.0")
            self.assertEqual(lines[1], "1e-06 2e-06 3e-06")


if __name__ == "__main__":
    unittest.main()
