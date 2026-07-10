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

    The current segment-file layout (see
    ``acquisition.save.write_waveform_file``) prepends two non-numeric
    header lines (the TSR timestamp and a literal ``wavedata`` token).
    A bare ``skip_lines=2`` happens to land on ``wavedata`` and
    crashes with ``ValueError``. We accept the legacy ``skip_lines``
    hint as a fast path and, when it is not enough, fall back to
    skipping every non-numeric header line until the first one that
    parses as ``float`` (so the parser survives header-format
    changes).
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    body = lines[skip_lines:] if skip_lines > 0 else lines
    data: list[float] = []
    for line in body:
        try:
            data.append(float(line.strip()))
        except ValueError:
            # Non-numeric header line (e.g. ``wavedata``). Keep
            # skipping until we hit actual samples.
            continue
    if not data:
        # Fallback: scan the whole file from the top, in case
        # ``skip_lines`` overshot the header (e.g. legacy 2-line
        # skip against a 4-line header).
        for line in lines:
            try:
                data.append(float(line.strip()))
            except ValueError:
                continue
    return np.array(data, dtype=float)


def count_files(path: str, prefix: str) -> Tuple[int, str]:
    """
    Count files starting with `prefix` inside `path` and read the first
    line of `<path>/<prefix>_0.txt` (used to extract the timestamp that
    feeds calculate_dcr).

    Mirrors the legacy daq_gui_func.count_files but tolerates a
    missing ``<prefix>_0.txt`` (returns ``"0"`` as the timestamp so
    the DCR calculation degrades to a ZeroDivisionError instead of
    a FileNotFoundError).
    """
    import os

    if not os.path.isdir(path):
        return 0, "0"

    files = os.listdir(path)
    count = sum(1 for f in files if f.startswith(prefix + "_"))
    first = os.path.join(path, f"{prefix}_0.txt")
    if not os.path.isfile(first):
        return count, "0"
    try:
        with open(first, "r", encoding="utf-8") as fh:
            time_line = fh.readline()
    except OSError:
        time_line = "0"
    return count, time_line


def read_timestamps(path: str, prefix: str) -> list[float]:
    """
    Read TSR timestamps from all ``<prefix>_N.txt`` files in *path*.

    Each segment file has the TSR value on its first line (a
    floating-point number).  Returns a sorted list of timestamps
    so consecutive differences are always positive.
    """
    import os

    if not os.path.isdir(path):
        return []

    timestamps: list[float] = []
    for fname in os.listdir(path):
        if not fname.startswith(prefix + "_"):
            continue
        try:
            with open(os.path.join(path, fname), encoding="utf-8") as fh:
                timestamps.append(float(fh.readline().strip()))
        except (ValueError, OSError):
            continue

    timestamps.sort()
    return timestamps


def calculate_dcr_from_timestamps(timestamps: list[float]) -> dict:
    """
    Compute DCR as the inverse of the mean time between consecutive files.

    ``timestamps`` should be a sorted list of TSR values (seconds).
    Returns::
        {"ok": True, "dcr_value": <Hz>, "error": None}
      or
        {"ok": False, "dcr_value": None, "error": "<reason>"}
    """
    if len(timestamps) < 2:
        return {"ok": False, "dcr_value": None,
                "error": "Need at least 2 timestamps"}

    diffs = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    mean_diff = sum(diffs) / len(diffs)

    if mean_diff <= 0:
        return {"ok": False, "dcr_value": None,
                "error": "Non-positive mean time difference"}

    dcr = round(1.0 / mean_diff, 2)
    return {"ok": True, "dcr_value": dcr, "error": None}


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
