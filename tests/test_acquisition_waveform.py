"""
Tests for acquisition/waveform_acquisition across the 3 scope dialects.

These tests inject a FakeConnection and assert that the right SCPI
commands are issued (matching ``old/daq_gui_func.start_wf`` and
``old/dictionary_SCPI.py``) and that the per-segment files / DATA.txt
/ zip end up on disk.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from acquisition import scpi_dictionary as ds
from acquisition.waveform_acquisition import (
    SCOPE_KEY,
    SCOPE_RTA,
    SCOPE_RTO,
    WaveformAcquisition,
)
from tests.fake_connection import FakeConnection


class RtaWaveformTests(unittest.TestCase):
    def test_rta_acquires_and_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = FakeConnection()
            # 3 segments available
            conn.set_response(ds.numCounts, "3")
            # Each query returns 4 comma-separated floats
            conn.set_default_response("0.1,0.2,0.3,0.4")
            # TSR per segment (ds.tsr = "CHAN:HIST:TSR?")
            conn.set_response_prefix(ds.tsr, "1700000000.0")
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

            # SCPI sanity: legacy sequence (RTA = RTO branch minus openHist).
            self.assertIn("STOP", conn.writes)
            self.assertIn(ds.ascii, conn.writes)        # FORM ASCii
            self.assertIn(ds.lsbf, conn.writes)         # FORM:BORD LSBF
            self.assertEqual(conn.queries.count(ds.numCounts), 1)        # ACQ:AVA?
            self.assertEqual(conn.queries.count(ds.waveform("1")), 3)    # CHAN1:DATA?
            self.assertEqual(conn.queries.count(ds.tsr), 3)              # CHAN:HIST:TSR?
            # openHist is only sent for RTO, not RTA.
            self.assertNotIn(ds.openHist("1"), conn.writes)
            # selectCurr is called once per segment with the descending
            # index -n+(i+1) (legacy ``CHAN:HIST:CURR``).
            for i in range(3):
                self.assertIn(ds.selectCurr(3, i), conn.writes)


class RtoWaveformTests(unittest.TestCase):
    def test_rto_enables_history_and_walks_buffer(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = FakeConnection()
            conn.set_response(ds.numCounts, "2")
            conn.set_default_response("0.5,0.6,0.7,0.8")
            conn.set_response_prefix(ds.tsr, "1700000000.0")
            conn.set_response(":TIM:SCAL?", "0.001")

            acq = WaveformAcquisition(
                scope_id=SCOPE_RTO, channel="1", time_seconds=0,
                save_root=tmp, name="rtorun",
            )
            acq.set_connection(conn)
            result = acq.run()

            # Files were written for each segment.
            for i in range(2):
                self.assertTrue(os.path.exists(os.path.join(result.path_d, f"rtorun_{i}.txt")))

            # RTO-specific: openHist(scope_id) = CHAN2:HIST:STAT ON is
            # written exactly once, before the per-segment loop.
            self.assertEqual(conn.writes.count(ds.openHist(SCOPE_RTO)), 1)

            # Walk through the history buffer with selectCurr for
            # each segment.
            self.assertIn(ds.selectCurr(2, 0), conn.writes)  # -2+1
            self.assertIn(ds.selectCurr(2, 1), conn.writes)  # -1+1 = 0 -> CHAN:HIST:CURR 0

            # Data and TSR queries use the channel-prefixed form.
            self.assertEqual(conn.queries.count(ds.waveform("1")), 2)
            self.assertEqual(conn.queries.count(ds.tsr), 2)


class KeyWaveformTests(unittest.TestCase):
    def test_key_segmented_stops_on_repeated_tsr(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = FakeConnection()
            # Legacy uses ds.numCountsKey (":ACQuire:SEGMented:COUNT?").
            conn.set_response(ds.numCountsKey, "5")
            conn.set_response(ds.waveformkey, "0.0,0.1,0.2")
            # TSRs: 1.0, 1.0 -> the second one matches prev, loop breaks
            tsrs = iter(["1.0", "1.0", "2.0", "3.0", "4.0"])
            original_query = conn.query

            def scripted_query(cmd):
                if cmd.startswith(":WAVeform:SEGMented:TTAG?"):
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

            # SCPI sanity: legacy KEY sequence.
            self.assertIn(":STOP", conn.writes)
            self.assertIn(ds.asciiKey, conn.writes)
            self.assertIn(ds.channelKey("2"), conn.writes)
            self.assertEqual(conn.queries.count(ds.numCountsKey), 1)
            # Legacy queries waveformkey once per attempted segment,
            # so the i=0 and i=1 iterations each issue a query (the
            # second one is the one whose TSR matches the first, which
            # triggers the break). 2 queries total, 1 file written.
            self.assertEqual(conn.queries.count(ds.waveformkey), 2)
            # selectCurrKey was used to index each attempted segment.
            self.assertIn(ds.selectCurrKey(5, 1), conn.writes)
            self.assertIn(ds.selectCurrKey(5, 2), conn.writes)


if __name__ == "__main__":
    unittest.main()
