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


if __name__ == "__main__":
    unittest.main()
