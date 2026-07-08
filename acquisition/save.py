"""
Pure save helpers extracted from lab_module / daq_gui_func legacy.

No GUI, no SCPI. Each function takes plain Python types and writes a
file. Used by the acquisition adapters and (later) by the GUI directly.
"""

from __future__ import annotations

import os
import shutil
from typing import Iterable, Optional, Sequence

import numpy as np


def ensure_dir(path: str) -> None:
    """Create the directory at path if it does not exist.

    Replaces ``lab_module.create_dir`` / ``lab_module.create_directory``.
    """
    os.makedirs(path, exist_ok=True)


def remove_path(path: str) -> None:
    """Remove a file or directory (no error if missing).

    Replaces ``lab_module.delete_dir`` / ``lab_module.delete_path``.
    """
    if not path:
        return
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def save_iv_text(path: str, v_values: Sequence[float], i_values: Sequence[float]) -> None:
    """Write IV arrays to a text file.

    Matches the legacy behaviour: two lines, voltage space-separated then
    current space-separated. Used by ``func.save_results_iv``.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(" ".join(str(v) for v in v_values) + "\n")
        f.write(" ".join(str(i) for i in i_values) + "\n")


def save_spectrum_text(path: str, name: str, data: Sequence[float]) -> None:
    """Write a spectrum charge histogram to a text file.

    Replaces ``func.save_results_spec``. Format: first line is
    ``min max``, subsequent lines are space-separated values with an
    auxiliary index sequence.
    """
    valuep = [float(v) for v in data]
    aux_len = np.arange(0, len(valuep), 1)
    with open(path + name + ".txt", "w", encoding="utf-8") as f_ile:
        f_ile.write(str(np.min(valuep)) + " " + str(np.max(valuep)) + "\n")
        for i in aux_len:
            f_ile.write(str(valuep[i]) + " ")


def write_waveform_file(path_dir: str, tsr: str, y_data: Iterable[float], index: int) -> str:
    """Write one waveform segment to ``<path_dir>/<name>_<index>.txt``.

    Replaces ``lab_module.file_writer_wf``. Returns the full path written.
    """
    name = os.path.basename(path_dir.rstrip("/\\"))
    full = os.path.join(path_dir, f"{name}_{index}.txt")
    with open(full, "w", encoding="utf-8") as f:
        f.write(str(tsr) + "\n")
        f.write("wavedata\n")
        for y in y_data:
            f.write(f"{float(y)}\n")
    return full


def write_waveform_metadata(path_data_txt: str, time_base: float, num_points: int,
                            start_time: float, scope: str) -> None:
    """Write the ``DATA.txt`` companion file.

    Replaces ``lab_module.create_data``. The legacy writes a header line
    plus the sample count and time base so ``count_files`` can read the
    timestamp back later.
    """
    remove_path(path_data_txt)
    with open(path_data_txt, "w", encoding="utf-8") as f:
        f.write(str(start_time) + "\n")
        f.write(f"scope={scope} time_base={time_base} num_points={num_points}\n")


def create_zip(path_dir: str, name: str, output_dir: Optional[str] = None) -> str:
    """Create a zip archive of ``path_dir`` and return the zip path.

    Replaces ``lab_module.create_zip`` / ``create_zip_archive``. Uses
    ``shutil.make_archive`` which produces ``<name>.zip``.

    By default the zip is written next to ``path_dir`` (i.e. in its
    parent directory). When ``output_dir`` is given, the zip is
    written into that directory instead — used by the waveform
    acquisition to keep the zip inside the run directory next to
    the segment files.
    """
    path_dir = path_dir.rstrip("/\\")
    base = os.path.basename(path_dir)
    if output_dir is None:
        parent = os.path.dirname(path_dir) or "."
        zip_root = os.path.join(parent, base)
    else:
        output_dir = output_dir.rstrip("/\\")
        zip_root = os.path.join(output_dir, base)
    archive = shutil.make_archive(zip_root, "zip",
                                  root_dir=os.path.dirname(path_dir) or ".",
                                  base_dir=base)
    return archive
