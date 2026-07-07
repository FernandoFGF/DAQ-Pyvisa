"""
Waveform acquisition adapter.

Mirrors ``daq_gui_func.start_wf`` (lines 702-849). The legacy captures
a segmented waveform acquisition: it spends ``time_seconds`` ticking
(``lm.chronometter``), then queries the scope ``numCounts`` times for
each segment, writes one file per segment, packages the result into a
zip and records a ``DATA.txt`` companion used later by the DCR/slider
analysis.

Three scope dialects are supported, same as the legacy:

  * scope 1 (RTA) and 2 (RTO): ``:WAV:MODE NORM`` then read with
    ``FORM ASC`` / ``FORM BORD`` depending on scope.
  * scope 3 (KEY): segmented acquisition with ``:WAV:MODE RAW``,
    iterates ``:WAV:SEGM:COUN`` segments, reads the per-segment TSR
    timestamp to detect duplicates.

The fake-friendly connection lets tests assert which SCPI commands
were sent in which order.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from acquisition.connection import InstrumentConnection, open_pyvisa
from acquisition.save import (
    create_zip,
    ensure_dir,
    remove_path,
    write_waveform_file,
    write_waveform_metadata,
)


SCOPE_RTA = "1"
SCOPE_RTO = "2"
SCOPE_KEY = "3"


@dataclass
class WaveformResult:
    path_d: str
    time_base: float
    num_points: int
    y_data: np.ndarray
    x_data: np.ndarray
    zip_path: str


class WaveformAcquisition:
    def __init__(self, scope_id: str = SCOPE_RTA, channel: str = "1",
                 time_seconds: float = 0.0, save_root: str = ".",
                 name: str = "waveform", config=None) -> None:
        self.scope_id = str(scope_id)
        self.channel = str(channel)
        self.time_seconds = float(time_seconds)
        self.save_root = save_root
        self.name = name
        self.config = config
        self._conn: Optional[InstrumentConnection] = None

    def set_connection(self, conn: InstrumentConnection) -> None:
        self._conn = conn

    def open(self) -> None:
        if self._conn is None:
            self._conn = open_pyvisa(f"scope{self.scope_id}", self.config)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "WaveformAcquisition":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> WaveformResult:
        self.open()
        conn = self._conn
        assert conn is not None

        # Build directory layout: <save_root>/<name> with subdir <name>
        path = os.path.join(self.save_root, self.name)
        ensure_dir(path)
        path_d = os.path.join(path, self.name)
        remove_path(path_d)
        ensure_dir(path_d)
        path_f = os.path.join(path_d, self.name)

        # Chronometer: legacy used ``lm.chronometter`` which is essentially
        # a ``time.sleep`` that prints progress. We replicate with a plain
        # sleep, no GUI side-effects.
        start_time = time.time()
        if self.time_seconds > 0:
            time.sleep(self.time_seconds)

        # Legacy: rta.timeout = 20000
        try:
            conn.timeout = 20000  # type: ignore[attr-defined]
        except AttributeError:
            pass

        y_data: np.ndarray = np.array([], dtype=float)
        if self.scope_id == SCOPE_KEY:
            y_data = self._acquire_key(conn, path_d, path_f, progress_callback)
        else:
            y_data = self._acquire_rta_or_rto(conn, path_f, progress_callback)

        # DATA.txt + zip
        time_base, num_points = self._infer_time_base_and_points(conn, y_data)
        path_fd = os.path.join(path_d, "DATA.txt")
        write_waveform_metadata(path_fd, time_base, num_points, start_time, self.scope_id)
        zip_path = create_zip(path, self.name)

        # Time axis: scope 3 used 10x, others 12x (legacy)
        if self.scope_id == SCOPE_KEY:
            x_data = np.linspace(0, time_base * 10, len(y_data))
        else:
            x_data = np.linspace(0, time_base * 12, len(y_data))

        return WaveformResult(
            path_d=path_d,
            time_base=time_base,
            num_points=num_points,
            y_data=y_data,
            x_data=x_data,
            zip_path=zip_path,
        )

    # ---- Per-dialect acquisition ----

    def _acquire_key(self, conn: InstrumentConnection, path_d: str, path_f: str,
                     progress_callback: Optional[Callable[[int, int], None]]) -> np.ndarray:
        """Keysight segmented acquisition (scope 3).

        Mirrors daq_gui_func.start_wf: write each segment's file only
        after the TSR has been checked against the previous one, so
        duplicate consecutive TSRs cause an early exit without writing.
        """
        conn.write(":STOP")
        conn.write(":WAV:MODE RAW")
        conn.write(f":WAV:SOUR CHAN{self.channel}")
        n_segments = int(conn.query(":WAV:SEGM:COUN?").strip())
        prev_tsr: Optional[str] = None
        y_data = np.array([], dtype=float)
        for i in range(n_segments):
            conn.write(f":WAV:SEGM:IND {i + 1}")
            raw = conn.query(":WAV:DATA?")
            cleaned = raw.strip().replace("\n", "").replace("\r", "")
            y_data = np.array(
                [float(x) for x in cleaned.split(",") if x.strip()],
                dtype=float,
            )
            tsr = conn.query(":WAV:SEGM:TTAG?").strip()
            if tsr == prev_tsr:
                break
            prev_tsr = tsr
            write_waveform_file(path_d, tsr, y_data, i)
            if progress_callback is not None:
                progress_callback(i + 1, n_segments)
        return y_data

    def _acquire_rta_or_rto(self, conn: InstrumentConnection, path_f: str,
                            progress_callback: Optional[Callable[[int, int], None]]) -> np.ndarray:
        """RTA/RTO per-segment read (scopes 1/2)."""
        conn.write("STOP")
        conn.write("FORM ASC")
        conn.write("FORM BORD LSBF")
        n_segments = int(conn.query(":WAV:COUN?").strip())
        if self.scope_id == SCOPE_RTO:
            conn.write(":HIST:STAT ON")
        y_data = np.array([], dtype=float)
        for i in range(n_segments):
            conn.write(f":WAV:SOUR CHAN{self.channel}")
            raw = conn.query(f":WAV:DATA?")
            y_data = np.array(
                [float(x) for x in raw.split(",") if x.strip()],
                dtype=float,
            )
            tsr = conn.query(":WAV:SEGM:TTAG?").strip()
            write_waveform_file(os.path.dirname(path_f), tsr, y_data, i)
            if progress_callback is not None:
                progress_callback(i + 1, n_segments)
        return y_data

    @staticmethod
    def _infer_time_base_and_points(conn: InstrumentConnection,
                                    y_data: np.ndarray) -> tuple[float, int]:
        """Ask the scope for time base, fall back to a 1e-3 default.

        The legacy used ``lm.create_data`` which queried
        ``:TIM:SCAL?`` (or similar) and computed ``time_base`` from
        the scope's reply. We do a single guarded query here and fall
        back to 1e-3 if the instrument does not respond.
        """
        try:
            tb = float(conn.query(":TIM:SCAL?").strip())
        except Exception:
            tb = 1e-3
        return tb, len(y_data)
