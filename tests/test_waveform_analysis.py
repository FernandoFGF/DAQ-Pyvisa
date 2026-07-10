"""
Parity tests for analysis/waveform_analysis vs the legacy helpers in
daq_gui_func: start_dcr, count_files, and the slider load/plot.
"""

from __future__ import annotations

import os
import textwrap
import unittest

import numpy as np

from analysis.waveform_analysis import (
    calculate_dcr_from_timestamps,
    count_files,
    load_waveform_file,
    make_time_axis,
    plot_waveform,
    read_timestamps,
)


class CalculateDcrFromTimestampsTests(unittest.TestCase):
    def test_basic(self):
        # 4 files spaced 0.5 s apart -> mean diff = 0.5 -> DCR = 2 Hz
        ts = [0.0, 0.5, 1.0, 1.5]
        res = calculate_dcr_from_timestamps(ts)
        self.assertTrue(res["ok"])
        self.assertAlmostEqual(res["dcr_value"], 2.0)

    def test_uneven_spacing(self):
        # 3 files at 0.0, 1.0, 3.0 -> diffs = [1.0, 2.0] -> mean = 1.5 -> 0.67 Hz
        ts = [0.0, 1.0, 3.0]
        res = calculate_dcr_from_timestamps(ts)
        self.assertTrue(res["ok"])
        self.assertAlmostEqual(res["dcr_value"], 0.67, places=2)

    def test_single_timestamp(self):
        res = calculate_dcr_from_timestamps([1.0])
        self.assertFalse(res["ok"])

    def test_empty_list(self):
        res = calculate_dcr_from_timestamps([])
        self.assertFalse(res["ok"])

    def test_negative_timestamps(self):
        # TSR values from the scope are negative (time before reference)
        ts = [-3.0, -2.0, -1.0]
        res = calculate_dcr_from_timestamps(ts)
        self.assertTrue(res["ok"])
        self.assertAlmostEqual(res["dcr_value"], 1.0)


class ReadTimestampsTests(unittest.TestCase):
    def test_reads_all_prefixed_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for i, t in enumerate([-3.0, -2.0, -1.0]):
                with open(os.path.join(tmp, f"run_{i}.txt"), "w", encoding="utf-8") as f:
                    f.write(f"{t}\nwavedata\n0.1\n")
            ts = read_timestamps(tmp, "run")
            self.assertEqual(ts, [-3.0, -2.0, -1.0])

    def test_ignores_non_prefixed_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "run_0.txt"), "w", encoding="utf-8") as f:
                f.write("-1.0\n")
            with open(os.path.join(tmp, "other.txt"), "w", encoding="utf-8") as f:
                f.write("99.0\n")
            ts = read_timestamps(tmp, "run")
            self.assertEqual(ts, [-1.0])

    def test_missing_directory(self):
        ts = read_timestamps("/nonexistent/path", "run")
        self.assertEqual(ts, [])

    def test_bad_timestamp_line(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "run_0.txt"), "w", encoding="utf-8") as f:
                f.write("not_a_number\n")
            ts = read_timestamps(tmp, "run")
            self.assertEqual(ts, [])


class LoadWaveformFileTests(unittest.TestCase):
    def test_skips_first_two_lines(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "wf_0.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("1700000000.0\n")
                f.write("metadata line\n")
                f.write("0.1\n0.2\n0.3\n0.4\n")
            data = load_waveform_file(p)
            np.testing.assert_array_equal(data, np.array([0.1, 0.2, 0.3, 0.4]))

    def test_custom_skip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "wf_0.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("h1\nh2\nh3\n1.0\n2.0\n")
            data = load_waveform_file(p, skip_lines=3)
            np.testing.assert_array_equal(data, np.array([1.0, 2.0]))

    def test_load_skips_non_numeric_header(self):
        """Real segment files are written with two non-numeric header
        lines: the TSR timestamp and the literal ``wavedata`` token.
        The legacy ``skip_lines=2`` would land on ``wavedata`` and
        raise ``ValueError: could not convert string to float``. The
        parser must skip non-numeric header lines instead."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "wf_0.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("1700000000.0\n")
                f.write("wavedata\n")
                f.write("0.5\n1.5\n2.5\n")
            data = load_waveform_file(p)
            np.testing.assert_array_equal(data, np.array([0.5, 1.5, 2.5]))

    def test_load_returns_empty_for_empty_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "wf_0.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("")
            data = load_waveform_file(p)
            self.assertEqual(data.size, 0)


class CountFilesTests(unittest.TestCase):
    def test_lists_prefixed_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                with open(os.path.join(tmp, f"run_{i}.txt"), "w", encoding="utf-8") as f:
                    f.write("-1.0\nx\ny\n")
            with open(os.path.join(tmp, "other_0.txt"), "w", encoding="utf-8") as f:
                f.write("ignored\n")
            count, time_line = count_files(tmp, "run")
            self.assertEqual(count, 3)
            self.assertEqual(time_line.strip(), "-1.0")

    def test_missing_zero_file_returns_zero_time(self):
        """When ``<prefix>_0.txt`` is missing (e.g. cooperative stop
        before the first segment finished writing), ``count_files``
        used to crash with FileNotFoundError. It now returns the
        actual count and a sentinel timestamp so DCR degrades to a
        ZeroDivisionError instead."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Files 1, 2, 3 exist but 0 does not (cooperative stop).
            for i in range(1, 4):
                with open(os.path.join(tmp, f"run_{i}.txt"), "w", encoding="utf-8") as f:
                    f.write("-1.0\n")
            count, time_line = count_files(tmp, "run")
            self.assertEqual(count, 3)
            self.assertEqual(time_line, "0")

    def test_missing_directory_returns_zero(self):
        count, time_line = count_files("/nonexistent/path", "run")
        self.assertEqual(count, 0)
        self.assertEqual(time_line, "0")


class MakeTimeAxisTests(unittest.TestCase):
    def test_default(self):
        t = make_time_axis(100)
        np.testing.assert_array_equal(t, np.linspace(0, 1000, 100))

    def test_custom_length(self):
        t = make_time_axis(50, length=200)
        np.testing.assert_array_equal(t, np.linspace(0, 200, 50))


class PlotWaveformSmokeTest(unittest.TestCase):
    def test_runs_without_error(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        data = np.array([0.0, 0.1, -0.1, 0.2, -0.2])
        plot_waveform(ax, data, num_points=len(data), length=10)
        self.assertEqual(ax.get_xlabel(), "Time(S)")
        self.assertEqual(ax.get_ylabel(), "Voltage(V)")
        plt.close(fig)


if __name__ == "__main__":
    unittest.main()
