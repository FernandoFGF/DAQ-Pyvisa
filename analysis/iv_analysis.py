"""
Pure analysis functions for IV curves.

Extracted from daq_gui_func.start_vbr, daq_gui_func.start_qr and
daq_gui_func.complete. No GUI, no I/O: take numpy arrays in, return
numpy arrays / plain numbers out. Plotting helpers are provided as a
thin wrapper around matplotlib that the GUI can call after computing.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


VBR_NEGATIVE_THRESHOLD = -0.01
QR_POSITIVE_THRESHOLD = 0.75


def _filter_negative(v_values: np.ndarray, i_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mask = v_values < VBR_NEGATIVE_THRESHOLD
    return v_values[mask], i_values[mask]


def _filter_positive(v_values: np.ndarray, i_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mask = v_values > QR_POSITIVE_THRESHOLD
    return v_values[mask], i_values[mask]


def calculate_vbr(v_values: np.ndarray, i_values: np.ndarray) -> dict:
    """
    Calculate the breakdown voltage (Vbr) from an IV curve.

    Mirrors the legacy algorithm in daq_gui_func.start_vbr:
      1. Keep only the negative section (v < VBR_NEGATIVE_THRESHOLD).
      2. Clip current to -1e-7 to avoid log/div by zero.
      3. Compute dI/dV and (dI/dV) / I.
      4. Drop the argmax of I (an outlier) before searching.
      5. Vbr is the voltage at which (dI/dV)/I is minimal.

    Args:
        v_values: voltage array (floats).
        i_values: current array (floats).

    Returns:
        Dict with keys:
          ok (bool), message (str), max_x (float), max_y (float),
          v_filtered, i_filtered, dydx_over_y (arrays for plotting).
    """
    v = np.asarray(v_values, dtype=float)
    i = np.asarray(i_values, dtype=float)

    if v.size == 0 or i.size == 0 or v.size != i.size:
        return {"ok": False, "message": "Empty or mismatched IV arrays"}

    v_neg, i_neg = _filter_negative(v, i)
    if v_neg.size == 0 or i_neg.size == 0:
        return {"ok": False, "message": "No se encuentran valores adecuados para calcular Vbr."}

    i_clipped = np.where(i_neg > -1e-7, -1e-7, i_neg)
    dydx = np.diff(i_clipped) / np.diff(v_neg)
    max_i = int(np.argmax(i_clipped))
    i_for_ratio = np.delete(i_clipped, max_i)
    dydx_over_y = dydx / i_for_ratio
    min_idx = int(np.argmin(dydx_over_y))
    max_x = float(v_neg[min_idx])
    max_y = float(i_for_ratio[min_idx])

    return {
        "ok": True,
        "max_x": max_x,
        "max_y": max_y,
        "v_filtered": v_neg,
        "i_filtered": i_neg,
        "i_clipped": i_clipped,
        "dydx": dydx,
        "dydx_over_y": dydx_over_y,
        "v_for_ratio": v_neg[1:],
    }


def calculate_qr(v_values: np.ndarray, i_values: np.ndarray,
                 v_range: Optional[Tuple[float, float]] = None) -> dict:
    """
    Calculate the quenching resistance (Qr) from an IV curve.

    The legacy algorithm in ``daq_gui_func.start_qr`` fit the
    full positive section above 0.75 V, which sometimes picked
    the wrong segment when the curve is not perfectly linear.
    The GUI now lets the user pick two endpoints on the plot
    and re-run the calculation; ``v_range`` carries the chosen
    voltage range ``(v_min, v_max)`` and overrides the default
    0.75 V threshold. When ``v_range`` is None the legacy
    behaviour is preserved.

    Algorithm:
      1. Keep positive section (v > 0.01).
      2. If v_range given, keep only the samples in that range
         (inclusive). Otherwise keep v > QR_POSITIVE_THRESHOLD.
      3. slope = (Imax - Imin) / (Vmax - Vmin).
      4. qr = round(1/slope, 1).

    Args:
        v_values: voltage array (floats).
        i_values: current array (floats).
        v_range: optional (v_min, v_max) tuple to restrict the
            fit to a user-selected segment of the positive
            section.

    Returns:
        Dict with ok, message, qr_value (str, e.g. "0.5"), slope,
        v_fit (x_fit endpoints), i_fit (y_fit endpoints),
        v_positive, i_positive.
    """
    v = np.asarray(v_values, dtype=float)
    i = np.asarray(i_values, dtype=float)

    if v.size == 0 or i.size == 0 or v.size != i.size:
        return {"ok": False, "message": "Empty or mismatched IV arrays"}

    mask_pos = v > 0.01
    v_pos = v[mask_pos]
    i_pos = i[mask_pos]
    if v_pos.size == 0 or i_pos.size == 0:
        return {"ok": False, "message": "No se encuentran valores adecuados para calcular Qr."}

    if v_range is not None:
        v_lo, v_hi = sorted(v_range)
        # The user moves the markers along the curve, so the
        # endpoints are not necessarily exact measurement
        # points. We treat the range as ``[v_lo, v_hi]``
        # inclusive so the QR reflects the curve behaviour
        # across the user-selected segment, even when the
        # markers land between two samples.
        mask_range = (v_pos >= v_lo) & (v_pos <= v_hi)
        v_high = v_pos[mask_range]
        i_high = i_pos[mask_range]
        if v_high.size < 2 or i_high.size < 2:
            return {"ok": False, "message": "No hay suficientes valores en el rango seleccionado para Qr."}
    else:
        mask_high = v_pos > QR_POSITIVE_THRESHOLD
        v_high = v_pos[mask_high]
        i_high = i_pos[mask_high]
        if v_high.size < 2 or i_high.size < 2:
            return {"ok": False, "message": "No hay suficientes valores por encima del umbral para Qr."}

    slope = (float(np.max(i_high)) - float(np.min(i_high))) / (
        float(np.max(v_high)) - float(np.min(v_high))
    )
    if slope == 0.0:
        return {"ok": False, "message": "La pendiente es cero; no se puede calcular Qr."}
    qr = f"{round(1.0 / slope, 1):.1f}"

    return {
        "ok": True,
        "qr_value": qr,
        "slope": slope,
        "v_fit": [float(np.min(v_high)), float(np.max(v_high))],
        "i_fit": [float(np.min(i_high)), float(np.max(i_high))],
        "v_positive": v_pos,
        "i_positive": i_pos,
    }


def plot_iv(ax, v_values, i_values, vbr_point=None, qr_line=None, dydx_over_y=None,
            v_for_ratio=None) -> None:
    """
    Legacy all-in-one plot. The new analysis paths use the
    dedicated helpers below; this entry point is kept for
    callers that still pass the legacy combination of
    arguments (e.g. the old ``plot_iv`` facade pass-through).
    """
    _reset_axes(ax)
    ax.set_xlabel("Voltios")
    ax.set_ylabel("Amperios")
    ax.plot(v_values, i_values)
    if vbr_point is not None:
        ax.plot(vbr_point[0], vbr_point[1], "ro")
    if qr_line is not None:
        ax.plot(qr_line[0], qr_line[1], "ro", linestyle="--")
    if dydx_over_y is not None and v_for_ratio is not None:
        ax2 = ax.twinx()
        ax2.plot(v_for_ratio, dydx_over_y, "r-")


def _reset_axes(ax) -> None:
    """Clear the primary axes and remove any twinx children.

    The Vbr plot helper creates a twinx for the secondary
    y-axis (the derivative); ``ax.cla()`` only clears the
    primary axes so the twinx would survive the next plot
    and overlay the new data. The Qr / Vbr / complete
    helpers call ``_reset_axes`` before drawing so the
    figure only shows what the current analysis wants.
    """
    fig = ax.get_figure()
    # Drop any secondary axes that share the same X axis.
    for other in list(fig.axes):
        if other is not ax and other.get_shared_x_axes().joined(other, ax):
            other.remove()
    ax.cla()
    # Re-tag the primary axes so the GUI's ``_get_canvas``
    # helper can find it even after a cla() wiped the
    # ylabel. We use the same string the plot helpers
    # would have set ('Amperios') to keep a single
    # canonical label.
    ax.set_ylabel("Amperios")


def plot_vbr(ax, v_filtered, i_filtered, vbr_point, dydx_over_y, v_for_ratio) -> None:
    """Draw the Vbr analysis on its own axes.

    Shows the negative portion of the IV curve (blue) plus the
    (dI/dV)/I derivative curve in red on a secondary y-axis.
    A red dot marks the Vbr point on both the IV curve and
    the derivative (it is plotted on the secondary axis so
    the user can see which minimum of the derivative was
    picked).
    """
    _reset_axes(ax)
    ax.set_xlabel("Voltios")
    ax.set_ylabel("Amperios")
    ax.plot(v_filtered, i_filtered, "b-", label="IV (negativa)")
    # Red dot on the IV curve at the calculated Vbr.
    if vbr_point is not None:
        ax.plot(vbr_point[0], vbr_point[1], "ro",
                markersize=8, label=f"Vbr = {vbr_point[0]:.4g} V")
    # Derivative on a secondary y-axis (right), in red.
    if dydx_over_y is not None and v_for_ratio is not None:
        ax2 = ax.twinx()
        ax2.set_ylabel("(dI/dV)/I", color="r")
        ax2.tick_params(axis="y", labelcolor="r")
        ax2.plot(v_for_ratio, dydx_over_y, "r-", label="(dI/dV)/I")
        # Mark the minimum of the derivative on the secondary
        # axis so the user can verify the choice.
        min_idx = int(np.argmin(dydx_over_y))
        ax2.plot(v_for_ratio[min_idx], dydx_over_y[min_idx], "ro",
                 markersize=8)
    # Combined legend: primary axis only (matplotlib does not
    # span legends across twinx cleanly).
    ax.legend(loc="upper left", fontsize=8)
    ax.autoscale(enable=True, axis="both", tight=True)


def plot_qr_initial(ax, v_positive, i_positive, v1=None, i1=None,
                    v2=None, i2=None) -> None:
    """Draw the positive section of the IV curve with two
    user-movable points (the future QR fit endpoints).

    By default the two markers are placed at the curve
    bounds (endpoint 1 at the smallest v, endpoint 2 at the
    largest v). The GUI passes explicit ``v1 / i1 / v2 / i2``
    when the user has dragged the markers before, or when
    the initial defaults should sit inside the data (e.g.
    both at the first positive sample so they never fall
    outside the measured range even when the user is
    zoomed in).

    The two red dots are pickable / draggable by the user
    (the GUI installs a PickEvent handler on them). When the
    user presses the QR button again the IV analyzer
    re-computes the fit between the new endpoints.
    """
    _reset_axes(ax)
    ax.set_xlabel("Voltios")
    ax.set_ylabel("Amperios")
    ax.plot(v_positive, i_positive, "b-", label="IV (positiva)")
    # Resolve the four endpoint coordinates. The defaults
    # land at the curve bounds, which the user can then
    # drag inward. Callers that want a specific initial
    # position (e.g. both at the first sample) pass them
    # explicitly.
    if v1 is None:
        v1 = float(v_positive[0])
        i1 = float(i_positive[0])
    if v2 is None:
        v2 = float(v_positive[-1])
        i2 = float(i_positive[-1])
    # Two separate pickable markers (one Line2D per dot)
    # so the GUI's pick handler can address each one
    # independently. We deliberately do NOT draw the
    # initial dashed fit line here: the user must press
    # the Qr button after moving the markers to see the
    # fit, so the first press is just a 'select the
    # segment you want to fit' prompt.
    ax.plot([v1], [i1], "ro", markersize=10, picker=5,
            label="Endpoint 1")
    ax.plot([v2], [i2], "ro", markersize=10, picker=5,
            label="Endpoint 2")
    ax.legend(loc="upper left", fontsize=8)
    ax.autoscale(enable=True, axis="both", tight=True)


def plot_qr_with_fit(ax, v_positive, i_positive, v_fit, i_fit) -> None:
    """Re-draw the positive section plus the final QR fit line
    through the user-selected endpoints.

    The two endpoints (v_fit[0]/i_fit[0] and v_fit[1]/i_fit[1])
    are highlighted in red so the user can see exactly which
    segment of the curve produced the fit.
    """
    _reset_axes(ax)
    ax.set_xlabel("Voltios")
    ax.set_ylabel("Amperios")
    ax.plot(v_positive, i_positive, "b-", label="IV (positiva)")
    if v_fit is not None and i_fit is not None:
        ax.plot(v_fit, i_fit, "r-", linewidth=2, label="Recta QR")
        ax.plot(v_fit, i_fit, "ro", markersize=8)
    ax.legend(loc="upper left", fontsize=8)
    ax.autoscale(enable=True, axis="both", tight=True)


def plot_complete(ax, v_values, i_values, vbr_point=None) -> None:
    """Draw the full IV curve: positive and negative sections.

    The whole measured sweep is rendered so the user sees
    the complete SiPM response, with the breakdown kink
    around 0 V and the linear quenching region on the
    positive side. The Vbr marker is preserved (a red dot
    on the negative section) if the user has computed one
    before; the secondary derivative axis and the QR fit
    overlay are dropped.
    """
    _reset_axes(ax)
    ax.set_xlabel("Voltios")
    ax.set_ylabel("Amperios")
    ax.plot(v_values, i_values, "b-", label="IV completa")
    if vbr_point is not None:
        ax.plot(vbr_point[0], vbr_point[1], "ro", markersize=8,
                label=f"Vbr = {vbr_point[0]:.4g} V")
    ax.legend(loc="upper left", fontsize=8)
    ax.autoscale(enable=True, axis="both", tight=True)
