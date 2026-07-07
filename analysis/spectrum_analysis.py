"""
Pure analysis functions for spectrum (charge histogram) data.

Extracted from daq_gui_func.finding_peaks. The legacy code:
  1. Parses the string stored in self.hist_data.
  2. Builds a 50-bin histogram.
  3. Calls scipy.signal.find_peaks with prominence=80.
  4. Plots histogram + line + 'x' markers on the peaks.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.signal import find_peaks
from matplotlib import colors
import matplotlib.pyplot as plt


DEFAULT_BINS = 50
DEFAULT_PROMINENCE = 80


def parse_hist_data(raw: str) -> np.ndarray:
    """
    Parse the legacy hist_data string format (parentheses, commas, spaces)
    into a numpy float array.
    """
    if not raw:
        return np.array([], dtype=float)
    cleaned = raw.replace("(", "").replace(")", "").replace(" ", "")
    parts = cleaned.split(",")
    return np.array([float(x) for x in parts if x.strip()], dtype=float)


def find_histogram_peaks(
    data: np.ndarray,
    bins: int = DEFAULT_BINS,
    prominence: float = DEFAULT_PROMINENCE,
) -> dict:
    """
    Build histogram and find peaks, mirroring daq_gui_func.finding_peaks.

    Returns:
      Dict with counts, bin_edges, bin_centers, peak_indices,
      peak_bin_centers, peak_heights, bins, prominence.
    """
    arr = np.asarray(data, dtype=float)
    if arr.size == 0:
        return {
            "ok": False,
            "message": "Primero debes de recoger datos que analizar.",
            "counts": np.array([]),
            "bin_edges": np.array([]),
            "bin_centers": np.array([]),
            "peak_indices": np.array([], dtype=int),
            "peak_bin_centers": np.array([]),
            "peak_heights": np.array([]),
        }

    counts, bin_edges = np.histogram(arr, bins=bins)
    bin_centers = bin_edges[1:]
    peaks, _ = find_peaks(counts, prominence=prominence)

    return {
        "ok": True,
        "counts": counts,
        "bin_edges": bin_edges,
        "bin_centers": bin_centers,
        "peak_indices": peaks,
        "peak_bin_centers": bin_centers[peaks] if peaks.size else np.array([]),
        "peak_heights": counts[peaks] if peaks.size else np.array([]),
        "bins": bins,
        "prominence": prominence,
    }


def plot_histogram_with_peaks(ax, data: np.ndarray, peaks_result: Optional[dict] = None,
                              bins: int = DEFAULT_BINS,
                              prominence: float = DEFAULT_PROMINENCE) -> dict:
    """
    Draw the legacy histogram (viridis-coloured bars + line trace + red 'x' peaks)
    on the given matplotlib axis. Returns the peaks_result dict.
    """
    if peaks_result is None:
        peaks_result = find_histogram_peaks(data, bins=bins, prominence=prominence)
    if not peaks_result.get("ok", False):
        return peaks_result

    ax.clear()
    counts = peaks_result["counts"]
    bin_edges = peaks_result["bin_edges"]
    fracs = counts / counts.max() if counts.max() > 0 else counts
    norm = colors.Normalize(fracs.min(), fracs.max()) if counts.size else None
    if norm is not None:
        _, _, patches = ax.hist(data, bins=bin_edges)
        for frac, patch in zip(fracs, patches):
            patch.set_facecolor(plt.cm.viridis(norm(frac)))
    ax.plot(peaks_result["bin_centers"], counts)
    if peaks_result["peak_indices"].size:
        ax.plot(
            peaks_result["peak_bin_centers"],
            peaks_result["peak_heights"],
            "rx",
        )
    ax.set_xlabel("Charge(Vs)")
    return peaks_result
