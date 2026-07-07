"""
Tests for acquisition/waveform_acquisition.

These tests inject a FakeConnection and assert that the right SCPI
commands are issued and that the per-segment files / DATA.txt / zip
end up on disk.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from acquisition.waveform_acquisition import (
    SCOPE_KEY,
    SCOPE_RTA,
    WaveformAcquisition,
)
from tests.fake_connection import FakeConnection


class RtaWaveformTests(unittest.TestCase):
    def test_rta_acquires_and_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = FakeConnection()
            conn.set_response(":WAV:COUN?", "3")
            # Each query returns 4 comma-separated floats
            conn.set_default_response("0.1,0.2,0.3,0.4")
            # TSR per segment
            conn.set_response_prefix(":WAV:SEGM:TTAG?", "1700000000.0")
            # Time base fallback
            conn.set_response(":TIM:SCAL?", "0.001")

            acq = WaveformAcquisition(
                scope_id=SCOPE_RTA, channel="1", time_seconds=0,
                save_root=tmp, name="run",
            )
            acq.set_connection(conn)
            result = acq.run()

            # Three files were written
            self.assertTrue(os.path.isdir(result.path_d))
            for i in range(3):
                self.assertTrue(os.path.exists(os.path.join(result.path_d, f"run_{i}.txt")))
            # DATA.txt was written
            self.assertTrue(os.path.exists(os.path.join(result.path_d, "DATA.txt")))
            # Zip was created
            self.assertTrue(os.path.isfile(result.zip_path))
            # Result has the expected shape
            self.assertEqual(len(result.y_data), 4)
            self.assertEqual(result.num_points, 4)

            # SCPI sanity
            self.assertIn("STOP", conn.writes)
            self.assertIn("FORM ASC", conn.writes)
            self.assertIn("FORM BORD LSBF", conn.writes)
            self.assertEqual(conn.queries.count(":WAV:COUN?"), 1)
            self.assertEqual(conn.queries.count(":WAV:DATA?"), 3)
            self.assertEqual(conn.queries.count(":WAV:SEGM:TTAG?"), 3)


class KeyWaveformTests(unittest.TestCase):
    def test_key_segmented_stops_on_repeated_tsr(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = FakeConnection()
            conn.set_response(":WAV:SEGM:COUN?", "5")
            conn.set_response(":WAV:DATA?", "0.0,0.1,0.2")
            # TSRs: 1.0, 1.0 -> the second one matches prev, loop breaks
            tsrs = iter(["1.0", "1.0", "2.0", "3.0", "4.0"])
            original_query = conn.query

            def scripted_query(cmd):
                if cmd.startswith(":WAV:SEGM:TTAG?"):
                    return next(tsrs)
                return original_query(cmd)

            conn.query = scripted_query  # type: ignore[assignment]
            conn.set_response(":TIM:SCAL?", "0.0005")

            acq = WaveformAcquisition(
                scope_id=SCOPE_KEY, channel="2", time_seconds=0,
                save_root=tmp, name="keyrun",
            )
            acq.set_connection(conn)
            result = acq.run()

            # First file (i=0) was written; the second iteration saw
            # prev_tsr == tsr and broke the loop without writing.
            self.assertTrue(os.path.exists(os.path.join(result.path_d, "keyrun_0.txt")))
            self.assertFalse(os.path.exists(os.path.join(result.path_d, "keyrun_1.txt")))
            self.assertFalse(os.path.exists(os.path.join(result.path_d, "keyrun_2.txt")))


if __name__ == "__main__":
    unittest.main()
