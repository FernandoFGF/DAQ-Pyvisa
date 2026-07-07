"""
Parity tests for analysis/spectrum_analysis vs daq_gui_func.finding_peaks.
"""

from __future__ import annotations

import unittest

import numpy as np

from analysis.spectrum_analysis import (
    DEFAULT_BINS,
    DEFAULT_PROMINENCE,
    find_histogram_peaks,
    parse_hist_data,
)


def _legacy_finding_peaks_logic(data: np.ndarray):
    from scipy.signal import find_peaks
    counts, bin_edges = np.histogram(data, bins=DEFAULT_BINS)
    bin_centers = bin_edges[1:]
    peaks, _ = find_peaks(counts, prominence=DEFAULT_PROMINENCE)
    return peaks, bin_centers, counts


class ParseHistDataTests(unittest.TestCase):
    def test_strips_parens_and_spaces(self):
        arr = parse_hist_data("(1.0, 2.0, 3.5, 4.1)")
        np.testing.assert_array_equal(arr, np.array([1.0, 2.0, 3.5, 4.1]))

    def test_empty(self):
        self.assertEqual(parse_hist_data("").size, 0)
        self.assertEqual(parse_hist_data(None).size, 0)


class FindHistogramPeaksTests(unittest.TestCase):
    def test_parity_against_legacy(self):
        rng = np.random.default_rng(42)
        data = np.concatenate([
            rng.normal(0, 0.1, 500),
            rng.normal(1.0, 0.1, 500),
            rng.normal(2.0, 0.1, 200),
        ])
        expected_peaks, expected_centers, expected_counts = _legacy_finding_peaks_logic(data)
        res = find_histogram_peaks(data)
        self.assertTrue(res["ok"])
        np.testing.assert_array_equal(res["peak_indices"], expected_peaks)
        np.testing.assert_array_equal(res["counts"], expected_counts)
        np.testing.assert_array_equal(res["bin_centers"], expected_centers)

    def test_empty(self):
        res = find_histogram_peaks(np.array([]))
        self.assertFalse(res["ok"])
        self.assertIn("recoger", res["message"])

    def test_uniform_data(self):
        data = np.random.default_rng(0).uniform(0, 1, 1000)
        res = find_histogram_peaks(data)
        self.assertTrue(res["ok"])


if __name__ == "__main__":
    unittest.main()
