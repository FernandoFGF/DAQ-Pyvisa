"""
Waveform acquisition adapter.

Mirrors ``daq_gui_func.start_wf`` (lines 702-849) and uses the SCPI
constants / helpers from the legacy ``old/dictionary_SCPI.py`` (now
homed in ``acquisition/scpi_dictionary``). The legacy captures a
segmented waveform acquisition: it spends ``time_seconds`` ticking
(``lm.chronometter``), then queries the scope ``numCounts`` times for
each segment, writes one file per segment, packages the result into a
zip and records a ``DATA.txt`` companion used later by the DCR/slider
analysis.

Three scope dialects are supported, exactly like the legacy:

  * scope 1 (RTA): per-segment read with the history buffer
    (``CHAN:HIST:CURR`` + ``CHAN:DATA?`` + ``CHAN:HIST:TSR?``).
  * scope 2 (RTO): same as RTA plus ``CHAN2:HIST:STAT ON`` to enable
    the history acquisition.
  * scope 3 (KEY): segmented acquisition driven by
    ``:ACQuire:SEGMented:COUNT?`` and ``:ACQuire:SEGMented:INDex <n>``,
    reads the per-segment TSR timestamp to detect duplicates.

The fake-friendly connection lets tests assert which SCPI commands
were sent in which order.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from acquisition import scpi_dictionary as ds
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
                 name: str = "waveform", config=None,
                 instrument_id: Optional[str] = None) -> None:
        self.scope_id = str(scope_id)
        self.channel = str(channel)
        self.time_seconds = float(time_seconds)
        self.save_root = save_root
        self.name = name
        self.config = config
        # ``instrument_id`` is the actual VISA resource id
        # (e.g. ``"scope1"``). When provided, ``open()`` uses it
        # verbatim; otherwise it falls back to the legacy
        # ``f"scope{scope_id}"`` mapping for backwards compatibility.
        self.instrument_id = instrument_id
        self._conn: Optional[InstrumentConnection] = None
        # When ``set_connection`` injects an externally-owned
        # connection (the one the Connect card is holding) we must
        # NOT close it on ``close()``; the GUI owns the lifetime and
        # will close it itself. When we opened the connection
        # ourselves, ``close()`` is the right place to release it.
        self._owns_connection: bool = False
        # Cooperative cancellation: set by ``request_stop()`` and
        # checked at the top of each per-segment loop. Mirrors the
        # pattern in ``SpectrumAcquisition``.
        self._stop_requested = False

    def request_stop(self) -> None:
        """Ask the running acquisition to stop after the current segment.

        Best-effort: the worker checks ``_stop_requested`` at the
        start of each segment, so a Stop request during a blocking
        ``conn.query`` will only take effect once that query returns.
        """
        self._stop_requested = True

    def set_connection(self, conn: InstrumentConnection) -> None:
        """Inject a connection (used by tests and by the GUI when the
        Connect tab already holds a live VISA session).

        The adapter will not close this connection on ``close()``;
        whoever injected it is responsible for its lifetime.
        """
        self._conn = conn
        self._owns_connection = False

    def open(self) -> None:
        if self._conn is None:
            target = self.instrument_id or f"scope{self.scope_id}"
            self._conn = open_pyvisa(target, self.config)
            self._owns_connection = True

    def close(self) -> None:
        if self._conn is not None and self._owns_connection:
            self._conn.close()
        self._conn = None
        self._owns_connection = False

    def __enter__(self) -> "WaveformAcquisition":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> WaveformResult:
        self.open()
        conn = self._conn
        assert conn is not None

        # Directory layout: <save_root>/<name>/ with the segment
        # files, DATA.txt and the zip all living side by side. No
        # nested <name>/<name>/ subdir.
        path = os.path.join(self.save_root, self.name)
        remove_path(path)
        ensure_dir(path)
        path_d = path  # back-compat alias used by the GUI / tests.

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
            y_data = self._acquire_key(conn, path, progress_callback)
        else:
            y_data = self._acquire_rta_or_rto(conn, path, progress_callback)

        # DATA.txt + zip
        time_base, num_points = self._infer_time_base_and_points(conn, y_data)
        path_fd = os.path.join(path, "DATA.txt")
        write_waveform_metadata(path_fd, time_base, num_points, start_time, self.scope_id)
        # Keep the zip inside the run directory, sibling of the data
        # files (output_dir=path). ``create_zip`` defaults to the
        # parent directory for back-compat with other callers.
        zip_path = create_zip(path, self.name, output_dir=path)

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

    def _acquire_key(self, conn: InstrumentConnection, path: str,
                     progress_callback: Optional[Callable[[int, int], None]]) -> np.ndarray:
        """Keysight segmented acquisition (scope 3).

        Mirrors ``daq_gui_func.start_wf`` exactly: the segment count
        comes from ``:ACQuire:SEGMented:COUNT?``, each segment is
        selected via ``:ACQuire:SEGMented:INDex <i>``, the waveform
        is read with ``:WAVeform:DATA?`` and the per-segment TSR
        timestamp with ``:WAVeform:SEGMented:TTAG?``. A repeated TSR
        triggers an early exit (no file is written for the duplicate).

        The legacy sequence issues ``*OPC?`` *after* the
        ``:WAVeform:DATA?`` read so the scope has time to flush the
        previous data block before the next ``:INDex`` write. Without
        that, Keysight occasionally drops the segment and the next
        query hangs until the connection times out.
        """
        conn.write(":STOP")
        conn.write(ds.asciiKey)
        conn.write(ds.channelKey(self.channel))
        n_segments = int(conn.query(ds.numCountsKey).strip())
        prev_tsr: Optional[str] = None
        y_data = np.array([], dtype=float)
        for i in range(n_segments):
            if self._stop_requested:
                print(f"[Waveform] {self.instrument_id or f'scope{self.scope_id}'} "
                      f"stop requested at segment {i}.")
                break
            conn.write(ds.selectCurrKey(n_segments, i + 1))
            raw = conn.query(ds.waveformkey)
            self._waiting(conn)
            cleaned = raw.strip().replace("\n", "").replace("\r", "")
            y_data = np.array(
                [float(x) for x in cleaned.split(",") if x.strip()],
                dtype=float,
            )
            tsr = conn.query(":WAVeform:SEGMented:TTAG?").strip()
            if tsr == prev_tsr:
                break
            prev_tsr = tsr
            write_waveform_file(path, tsr, y_data, i)
            if progress_callback is not None:
                progress_callback(i + 1, n_segments)
        return y_data

    def _acquire_rta_or_rto(self, conn: InstrumentConnection, path: str,
                            progress_callback: Optional[Callable[[int, int], None]]) -> np.ndarray:
        """RTA (scope 1) and RTO (scope 2) per-segment read.

        The legacy path enables the scope's history buffer
        (``CHAN2:HIST:STAT ON`` for RTO) and then walks through the
        buffer with ``CHAN:HIST:CURR <n>``, reading
        ``CHAN<channel>:DATA?`` and ``CHAN:HIST:TSR?`` for each
        segment. ``CHAN:HIST:CURR`` is given as ``-trigg + (i+1)``,
        so segment ``i=0`` maps to ``-trigg+1`` (the oldest entry)
        and ``i=trigg-1`` to ``1`` (the most recent).
        """
        conn.write("STOP")
        conn.write(ds.ascii)
        conn.write(ds.lsbf)
        n_segments = int(conn.query(ds.numCounts).strip())
        if self.scope_id == SCOPE_RTO:
            conn.write(ds.openHist(self.scope_id))
        y_data = np.array([], dtype=float)
        for i in range(n_segments):
            if self._stop_requested:
                print(f"[Waveform] {self.instrument_id or f'scope{self.scope_id}'} "
                      f"stop requested at segment {i}.")
                break
            conn.write(ds.selectCurr(n_segments, i))
            y_aux = conn.query(ds.waveform(self.channel))
            y_data = np.array(
                [float(x) for x in y_aux.split(",") if x.strip()],
                dtype=float,
            )
            self._waiting(conn)
            tsr = conn.query(ds.tsr)
            write_waveform_file(path, tsr, y_data, i)
            if progress_callback is not None:
                progress_callback(i + 1, n_segments)
        return y_data

    @staticmethod
    def _waiting(conn: InstrumentConnection) -> None:
        """Block until the scope reports ``*OPC`` (operation complete).

        Mirrors the legacy ``lm.waiting(rta)`` call. The fake test
        connection answers ``*OPC?`` with an empty string by default,
        which is fine for tests; on real hardware this gives the scope
        a moment to finish the pending command.
        """
        try:
            conn.query(ds.rdy)
        except Exception:
            pass

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
