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
    calculate_dcr,
    count_files,
    load_waveform_file,
    make_time_axis,
    plot_waveform,
)


class CalculateDcrTests(unittest.TestCase):
    def test_basic(self):
        # 100 files, time_str "-1.5" -> 100 / 1.5 = 66.666... -> 66.67
        res = calculate_dcr(100, "-1.5")
        self.assertTrue(res["ok"])
        self.assertAlmostEqual(res["dcr_value"], 66.67, places=2)

    def test_zero_division(self):
        res = calculate_dcr(10, "0")
        self.assertFalse(res["ok"])

    def test_bad_time_string(self):
        res = calculate_dcr(10, "not_a_number")
        self.assertFalse(res["ok"])


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
