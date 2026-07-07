"""
Tests for acquisition/iv_acquisition.
"""

from __future__ import annotations

import os
import unittest

from acquisition.iv_acquisition import IVAcquisition
from tests.fake_connection import FakeConnection


class IVAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = FakeConnection()
        # ``*OPC?`` returns '1' so the wait loop exits immediately.
        self.conn.set_response("*OPC?", "1")
        # ``:FETC:ARR:CURR?`` and ``:FETC:ARR:VOLT?`` return comma-separated
        # samples. Tests override per-case.
        self.conn.set_default_response("")

    def test_run_uses_correct_scpi_sequence(self):
        self.conn.set_response(":FETC:ARR:CURR?", "0.1,0.2,0.3")
        self.conn.set_response(":FETC:ARR:VOLT?", "1.0,0.5,0.0")
        acq = IVAcquisition("smu", v_start=1.0, v_stop=0.0, v_step=0.5)
        acq.set_connection(self.conn)
        result = acq.run()
        self.assertEqual(len(result.voltage), 3)
        self.assertEqual(len(result.current), 3)
        self.assertEqual(result.points, 2)

        # Assert the SCPI sequence is the one the legacy code used.
        self.assertIn("*RST", self.conn.writes)
        self.assertIn(":SOUR:FUNC:MODE VOLT", self.conn.writes)
        self.assertIn(":SOUR:SWE:MODE SWE", self.conn.writes)
        self.assertIn(":SOUR:SWE:STA SING", self.conn.writes)
        self.assertIn(":SOUR:SWE:SPAC LIN", self.conn.writes)
        self.assertIn(":SOUR:VOLT:STAR 1.0", self.conn.writes)
        self.assertIn(":SOUR:VOLT:STOP 0.0", self.conn.writes)
        self.assertIn(":SOUR:VOLT:POIN 2", self.conn.writes)
        self.assertIn(":OUTP ON", self.conn.writes)
        self.assertIn(":INIT", self.conn.writes)
        self.assertIn(":OUTP OFF", self.conn.writes)
        self.assertIn(":FETC:ARR:CURR?", self.conn.queries)
        self.assertIn(":FETC:ARR:VOLT?", self.conn.queries)
        self.assertIn("*OPC?", self.conn.queries)

    def test_run_returns_parsed_arrays(self):
        self.conn.set_response(":FETC:ARR:CURR?", "1e-6,2e-6,3e-6,4e-6")
        self.conn.set_response(":FETC:ARR:VOLT?", "1.0,0.5,0.0,-0.5")
        acq = IVAcquisition("smu", v_start=1.0, v_stop=-0.5, v_step=0.5)
        acq.set_connection(self.conn)
        result = acq.run()
        self.assertEqual(list(result.voltage), [1.0, 0.5, 0.0, -0.5])
        self.assertEqual(list(result.current), [1e-6, 2e-6, 3e-6, 4e-6])

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
