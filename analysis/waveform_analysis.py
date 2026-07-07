"""
Pure analysis functions for waveform (DCR + waveform file loading).

Extracted from daq_gui_func.start_dcr and the slider_event /
decrease_slider_value / increase_slider_value trio. No GUI, no I/O.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def calculate_dcr(num_files: int, time_str: str) -> dict:
    """
    Compute Data Collection Rate (DCR) = num_files / (-time_str).

    Mirrors daq_gui_func.start_dcr (the legacy uses -float(time_str) as
    the denominator; time_str is the first line of the waveform DATA.txt).

    Returns:
      Dict with ok, dcr_value, error.
    """
    try:
        dcr = round(num_files / (-float(time_str)), 2)
        return {"ok": True, "dcr_value": dcr, "error": None}
    except (ValueError, ZeroDivisionError) as e:
        return {"ok": False, "dcr_value": None, "error": str(e)}


def load_waveform_file(path: str, skip_lines: int = 2) -> np.ndarray:
    """
    Read a waveform file, skipping the first `skip_lines` lines.

    Mirrors the common path used by slider_event / decrease / increase:
      with open(path, 'r') as f:
          lines = f.readlines()[skip_lines:]
      data = [float(line.strip()) for line in lines]
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[skip_lines:]
    return np.array([float(line.strip()) for line in lines], dtype=float)


def count_files(path: str, prefix: str) -> Tuple[int, str]:
    """
    Count files starting with `prefix` inside `path` and read the first
    line of `<path>/<prefix>_0.txt` (used to extract the timestamp that
    feeds calculate_dcr).

    Mirrors the legacy daq_gui_func.count_files.
    """
    import os

    if not os.path.isdir(path):
        return 0, "0"

    files = os.listdir(path)
    count = sum(1 for f in files if f.startswith(prefix + "_"))
    first = os.path.join(path, f"{prefix}_0.txt")
    with open(first, "r", encoding="utf-8") as fh:
        time_line = fh.readline()
    return count, time_line


def make_time_axis(num_points: int, length: int = 1000) -> np.ndarray:
    """
    Build the time axis used by slider_event: np.linspace(0, 1000, num_points).
    """
    return np.linspace(0, length, int(num_points))


def plot_waveform(ax, data: np.ndarray, num_points: int, length: int = 1000) -> None:
    """
    Draw a waveform on the given axis. Mirrors the legacy slider plotting.
    """
    ax.clear()
    ax.plot(make_time_axis(num_points, length=length), data)
    ax.set_xlabel("Time(S)")
    ax.set_ylabel("Voltage(V)")
