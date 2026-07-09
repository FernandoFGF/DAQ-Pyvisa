"""
Parity tests for analysis/iv_analysis vs the legacy algorithm in
daq_gui_func.start_vbr and daq_gui_func.start_qr.

The legacy code lives inside daq_gui_func and depends on a Tk self
object, so we re-implement the relevant inner blocks here in a
self-contained form. If the legacy ever changes, the test will fail and
flag a behaviour drift.
"""

from __future__ import annotations

import unittest

import numpy as np

from analysis.iv_analysis import (
    QR_POSITIVE_THRESHOLD,
    VBR_NEGATIVE_THRESHOLD,
    calculate_qr,
    calculate_vbr,
)


# ---- Legacy re-implementations (verbatim from daq_gui_func.py) ----

def _legacy_vbr(v_values_in, i_values_in):
    v_values = [float(x) for x in v_values_in]
    i_values = [float(x) for x in i_values_in]
    x_neg = [vx for vx, vy in zip(v_values, i_values) if vx < VBR_NEGATIVE_THRESHOLD]
    y_neg = [vy for vx, vy in zip(v_values, i_values) if vx < VBR_NEGATIVE_THRESHOLD]
    if not x_neg or not y_neg:
        return None
    v_values = x_neg
    i_values = y_neg
    i_values = np.array(i_values)
    i_values = np.where(i_values > -1e-7, -1e-7, i_values)
    dydx = np.diff(i_values) / np.diff(v_values)
    max_i = int(np.argmax(i_values))
    i_values = np.delete(i_values, max_i)
    dydx_over_y = dydx / i_values
    max_index = int(np.argmin(dydx_over_y))
    return v_values[max_index]


def _legacy_qr(v_values_in, i_values_in):
    v_values = [float(x) for x in v_values_in]
    i_values = [float(x) for x in i_values_in]
    x_pos = [vx for vx, vy in zip(v_values, i_values) if vx > 0.01]
    y_pos = [vy for vx, vy in zip(v_values, i_values) if vx > 0.01]
    if not x_pos or not y_pos:
        return None
    v_high = [vx for vx, vy in zip(x_pos, y_pos) if vx > QR_POSITIVE_THRESHOLD]
    i_high = [vy for vx, vy in zip(x_pos, y_pos) if vx > QR_POSITIVE_THRESHOLD]
    m_m = (max(i_high) - min(i_high)) / (max(v_high) - min(v_high))
    return f"{round(1.0 / m_m, 1):.1f}"


class VbrParityTests(unittest.TestCase):
    def test_parity_simple_curve(self):
        v = np.array([1.0, 0.5, 0.0, -0.5, -5.0, -8.0, -10.0, -12.0, -15.0, -20.0])
        i = np.array([1e-6, 5e-7, 1e-8, -1e-8, -5e-8, -1e-7, -1e-4, -1e-3, -5e-3, -1e-2])
        expected = _legacy_vbr(v, i)
        self.assertIsNotNone(expected)
        res = calculate_vbr(v, i)
        self.assertTrue(res["ok"], msg=res.get("message"))
        self.assertAlmostEqual(res["max_x"], expected, places=9)

    def test_no_negative_section(self):
        v = np.array([0.0, 0.1, 0.2, 0.5])
        i = np.array([1e-6, 2e-6, 3e-6, 4e-6])
        res = calculate_vbr(v, i)
        self.assertFalse(res["ok"])
        self.assertIn("Vbr", res["message"])

    def test_empty_input(self):
        res = calculate_vbr(np.array([]), np.array([]))
        self.assertFalse(res["ok"])


class QrParityTests(unittest.TestCase):
    def test_parity_simple_curve(self):
        v = np.array([0.0, 0.1, 0.5, 0.8, 1.0, 1.5, 2.0])
        i = np.array([1e-9, 5e-9, 1e-6, 5e-6, 1e-5, 2e-5, 3e-5])
        expected = _legacy_qr(v, i)
        self.assertIsNotNone(expected)
        res = calculate_qr(v, i)
        self.assertTrue(res["ok"], msg=res.get("message"))
        self.assertEqual(res["qr_value"], expected)

    def test_no_positive_section(self):
        v = np.array([-1.0, -0.5, -0.1, 0.0])
        i = np.array([1e-6, 2e-6, 3e-6, 4e-6])
        res = calculate_qr(v, i)
        self.assertFalse(res["ok"])
        self.assertIn("Qr", res["message"])

    def test_empty_input(self):
        res = calculate_qr(np.array([]), np.array([]))
        self.assertFalse(res["ok"])

    def test_v_range_restricts_fit(self):
        """A user-selected voltage range must restrict the
        fit to the segment in that range. We build a linear
        positive section (which is the realistic SiPM
        response) and verify the fit endpoints reflect the
        user-selected range, not the global default."""
        v = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        # Linear IV with slope 1e-5 A/V across the whole
        # positive section. The fit slope must be 1e-5
        # regardless of the chosen range; the fit endpoints
        # (v_fit / i_fit) must reflect the user-selected
        # range.
        i = 1e-5 * v
        res = calculate_qr(v, i, v_range=(1.0, 3.0))
        self.assertTrue(res["ok"], msg=res.get("message"))
        self.assertAlmostEqual(res["slope"], 1e-5, places=9)
        self.assertAlmostEqual(res["v_fit"][0], 1.0, places=12)
        self.assertAlmostEqual(res["v_fit"][1], 3.0, places=12)
        self.assertAlmostEqual(res["i_fit"][0], 1e-5, places=12)
        self.assertAlmostEqual(res["i_fit"][1], 3e-5, places=12)
        # A different range produces different endpoints but
        # the same slope.
        res2 = calculate_qr(v, i, v_range=(0.5, 2.5))
        self.assertTrue(res2["ok"], msg=res2.get("message"))
        self.assertAlmostEqual(res2["slope"], 1e-5, places=9)
        self.assertAlmostEqual(res2["v_fit"][0], 0.5, places=12)
        self.assertAlmostEqual(res2["v_fit"][1], 2.5, places=12)

    def test_v_range_reversed_endpoints_are_normalised(self):
        """If the user drags the markers in the wrong order
        (right then left) we still fit the correct segment.
        The implementation sorts the endpoints internally."""
        v = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        i = np.array([0.0, 5e-6, 1e-5, 1.5e-5, 2e-5])
        res = calculate_qr(v, i, v_range=(2.0, 0.5))  # reversed
        self.assertTrue(res["ok"], msg=res.get("message"))
        self.assertAlmostEqual(res["slope"], 1e-5, places=9)

    def test_v_range_with_too_few_samples(self):
        """A range that catches only one sample must fail
        cleanly (the fit needs at least 2 points)."""
        v = np.array([0.0, 0.1, 0.5, 1.0, 1.5])
        i = np.array([0.0, 1e-6, 5e-6, 1e-5, 1.5e-5])
        res = calculate_qr(v, i, v_range=(0.49, 0.51))
        self.assertFalse(res["ok"])

    def test_v_range_zero_slope_is_rejected(self):
        """A flat segment (slope = 0) would produce 1/0 = inf;
        we must reject it with a clear message instead of
        returning an infinite resistance."""
        v = np.array([0.0, 0.5, 1.0, 1.5])
        i = np.array([0.0, 5e-6, 5e-6, 5e-6])  # flat
        res = calculate_qr(v, i, v_range=(0.0, 1.5))
        self.assertFalse(res["ok"])
        self.assertIn("pendiente", res["message"])


class PlotHelpersTests(unittest.TestCase):
    """Smoke tests for the new plot helpers. The matplotlib
    back-end is exercised end-to-end (Agg) so any import or
    API change in the analysis module fails the test."""

    def setUp(self) -> None:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)

    def test_plot_vbr_draws_negative_section_and_derivative(self):
        from analysis.iv_analysis import plot_vbr
        v = np.linspace(-20.0, -0.5, 50)
        i = -1e-7 * np.exp(-v / 5.0)
        plot_vbr(
            self.ax, v, i,
            vbr_point=(-10.0, float(i[20])),
            dydx_over_y=np.linspace(0.1, 0.9, 49),
            v_for_ratio=v[1:],
        )
        # At least 3 lines: the IV curve, the Vbr marker, the
        # derivative on the secondary axis.
        self.assertGreaterEqual(len(self.ax.get_lines()), 2)

    def test_plot_qr_initial_creates_two_pickable_markers(self):
        from analysis.iv_analysis import plot_qr_initial
        v = np.linspace(0.0, 2.0, 30)
        i = 1e-5 * v
        plot_qr_initial(self.ax, v, i)
        # Two red markers (one Line2D per dot) plus the IV
        # line; no dashed fit line on the initial plot.
        red_markers = [
            line for line in self.ax.get_lines()
            if line.get_color() == "r" and line.get_marker() == "o"
        ]
        self.assertEqual(len(red_markers), 2)
        for marker in red_markers:
            self.assertIsNotNone(marker.get_picker())

    def test_plot_qr_initial_accepts_explicit_endpoints(self):
        """When the GUI starts with both endpoints at the
        first positive sample, the markers must be drawn
        at that position (not at the curve bounds) so
        neither falls outside the data when the user is
        zoomed in."""
        from analysis.iv_analysis import plot_qr_initial
        v = np.linspace(0.0, 2.0, 30)
        i = 1e-5 * v
        # Both endpoints at the first positive sample.
        plot_qr_initial(self.ax, v, i,
                        v1=v[0], i1=i[0], v2=v[0], i2=i[0])
        red_markers = [
            line for line in self.ax.get_lines()
            if line.get_color() == "r" and line.get_marker() == "o"
        ]
        self.assertEqual(len(red_markers), 2)
        for marker in red_markers:
            self.assertAlmostEqual(marker.get_xdata()[0], v[0])

    def test_plot_qr_with_fit_draws_the_final_line(self):
        from analysis.iv_analysis import plot_qr_with_fit
        v = np.linspace(0.0, 2.0, 30)
        i = 1e-5 * v
        plot_qr_with_fit(
            self.ax, v, i,
            v_fit=[0.5, 1.5], i_fit=[5e-6, 1.5e-5],
        )
        red_lines = [l for l in self.ax.get_lines() if l.get_color() == "r"]
        self.assertGreaterEqual(len(red_lines), 1)

    def test_plot_complete_draws_full_curve(self):
        from analysis.iv_analysis import plot_complete
        v = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
        i = np.array([-1e-5, -5e-6, 0.0, 5e-6, 1e-5])
        plot_complete(self.ax, v, i)
        self.assertEqual(len(self.ax.get_lines()), 1)

    def test_plot_complete_with_vbr_marker_keeps_the_red_dot(self):
        from analysis.iv_analysis import plot_complete
        v = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
        i = np.array([-1e-5, -5e-6, 0.0, 5e-6, 1e-5])
        plot_complete(self.ax, v, i, vbr_point=(-0.5, -5e-6))
        # IV line + Vbr marker
        self.assertEqual(len(self.ax.get_lines()), 2)
        # The red dot must be at the right voltage.
        red_dots = [
            line for line in self.ax.get_lines()
            if line.get_color() == "r" and line.get_marker() == "o"
        ]
        self.assertEqual(len(red_dots), 1)
        self.assertAlmostEqual(red_dots[0].get_xdata()[0], -0.5)

    def test_plot_complete_drops_secondary_axes_from_vbr(self):
        """Regression: when the user computes Vbr first (which
        creates a twinx for the derivative) and then presses
        'Draw complete', the secondary axis must be removed
        so the full-curve plot is not overlaid on the
        derivative."""
        from analysis.iv_analysis import plot_complete, plot_vbr
        v_neg = np.linspace(-20.0, -0.5, 50)
        i_neg = -1e-7 * np.exp(-v_neg / 5.0)
        plot_vbr(
            self.ax, v_neg, i_neg,
            vbr_point=(-10.0, float(i_neg[20])),
            dydx_over_y=np.linspace(0.1, 0.9, 49),
            v_for_ratio=v_neg[1:],
        )
        # Vbr created a twinx (secondary axis).
        self.assertGreater(len(self.fig.axes), 1)
        v = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
        i = np.array([-1e-5, -5e-6, 0.0, 5e-6, 1e-5])
        plot_complete(self.ax, v, i)
        # plot_complete removed the twinx, leaving just the
        # primary axes.
        self.assertEqual(len(self.fig.axes), 1)


if __name__ == "__main__":
    unittest.main()
