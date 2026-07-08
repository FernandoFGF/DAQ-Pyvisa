"""
Spectrum (charge histogram) acquisition adapter.

Mirrors ``daq_gui_func.start_spectrum`` exactly, including the three
oscilloscope dialects the legacy supports:

  * scope 1 (RTA, R&S RTA4000 series): two cursor position queries at
    ``CURSor1:Y1Position?`` / ``CURSor1:Y2Position?`` (each gated by
    ``*OPC?``), charge = p_1 - p_2. The cursor source is set with
    ``CURSor1:SOURce <channel>``.
  * scope 2 (RTO, R&S RTO2000 series): single ``MEAS1:RES:ACT?`` query
    after the cursor source is set.
  * scope 3 (KEY, Keysight): ``:SYSTem:HEADer OFF`` +
    ``:MEASure:STATistics CURRENT`` + ``:MEASure1:RESults?``.

The adapter also calls back every 100 samples so a GUI can redraw the
histogram, matching the legacy behaviour of ``self.canvas.draw()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from acquisition.connection import InstrumentConnection, open_pyvisa
from acquisition import scpi_dictionary as ds


SCOPE_RTA = "1"
SCOPE_RTO = "2"
SCOPE_KEY = "3"


@dataclass
class SpectrumResult:
    data: np.ndarray
    scope: str
    channel: str
    num_datos: int


class SpectrumAcquisition:
    def __init__(self, scope_id: str = SCOPE_RTA, channel: str = "MA1",
                 num_datos: int = 100, config=None,
                 instrument_id: Optional[str] = None) -> None:
        self.scope_id = str(scope_id)
        self.channel = str(channel)
        self.num_datos = int(num_datos)
        self.config = config
        # ``instrument_id`` is the actual VISA resource id
        # (e.g. ``"scope1"``). When provided, ``open()`` uses it
        # verbatim; otherwise it falls back to the legacy
        # ``f"scope{scope_id}"`` mapping for backwards compatibility.
        self.instrument_id = instrument_id
        self._conn: Optional[InstrumentConnection] = None
        # Cooperative cancellation: set by ``request_stop()`` and
        # checked between samples so the worker finishes the current
        # iteration and exits cleanly.
        self._stop_requested = False

    def set_connection(self, conn: InstrumentConnection) -> None:
        self._conn = conn

    def request_stop(self) -> None:
        """Ask the running acquisition to stop after the current sample.

        Best-effort: the worker checks ``_stop_requested`` between
        samples, so a Stop request during a blocking ``conn.query``
        will only take effect once that query returns (or times out).
        """
        self._stop_requested = True

    def open(self) -> None:
        if self._conn is None:
            target = self.instrument_id or f"scope{self.scope_id}"
            self._conn = open_pyvisa(target, self.config)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __enter__(self) -> "SpectrumAcquisition":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(self, progress_callback: Optional[Callable[[np.ndarray], None]] = None) -> SpectrumResult:
        """Acquire ``num_datos`` charge samples and return them.

        ``progress_callback`` is called every 100 samples with the
        accumulated data so far. Tests pass a list-append function or
        None.
        """
        self.open()
        conn = self._conn
        assert conn is not None

        # Set a sane default timeout. The legacy code did
        # ``del conn.timeout`` which disabled the timeout entirely and
        # caused the worker to hang forever if the scope stopped
        # responding. 20 s is the same value the waveform adapter
        # uses; per-query timeouts inside ``_read_one`` are tighter.
        try:
            conn.timeout = 20000  # type: ignore[attr-defined]
        except AttributeError:
            pass

        scope_label = self.instrument_id or f"scope{self.scope_id}"
        print(f"[Spectrum] {scope_label} started: {self.num_datos} samples "
              f"on channel {self.channel}")

        x_values: List[float] = []
        stopped = False
        for i in range(1, self.num_datos + 1):
            if self._stop_requested:
                stopped = True
                print(f"[Spectrum] {scope_label} stop requested at sample {i - 1}.")
                break
            r_r = self._read_one(conn)
            x_values.append(r_r)

            if progress_callback is not None and i % 100 == 0:
                progress_callback(np.array(x_values, dtype=float))
                print(f"[Spectrum] {scope_label} progress: {i}/{self.num_datos} samples")

        print(f"[Spectrum] {scope_label} done: collected {len(x_values)} samples")
        return SpectrumResult(
            data=np.array(x_values, dtype=float),
            scope=self.scope_id,
            channel=self.channel,
            num_datos=self.num_datos,
        )

    def _read_one(self, conn: InstrumentConnection) -> float:
        """Read a single charge sample using the scope's dialect.

        Each ``conn.query`` is wrapped with a per-query timeout so a
        frozen scope fails fast (5 s) instead of hanging the whole
        worker. The original timeout is restored after each call.

        The SCPI command sequence mirrors ``daq_gui_func.start_spectrum``
        in the legacy ``old/`` module, using the constants in
        ``acquisition/scpi_dictionary`` (sourced from the original
        ``old/dictionary_SCPI.py``).
        """
        if self.scope_id == SCOPE_RTA:
            conn.write("FORM BIN")
            conn.write(ds.selectChanCur(self.channel))
            if conn.query(ds.rdy):
                p_1 = float(self._query_with_timeout(conn, ds.posC1))
            else:
                p_1 = 0.0
            if conn.query(ds.rdy):
                p_2 = float(self._query_with_timeout(conn, ds.posC2))
            else:
                p_2 = 0.0
            return p_1 - p_2

        if self.scope_id == SCOPE_RTO:
            conn.write("FORM BIN")
            conn.write(ds.selectChanCur(self.channel))
            return self._query_with_timeout(conn, "MEAS1:RES:ACT? ")

        if self.scope_id == SCOPE_KEY:
            conn.write(ds.headerOff)
            conn.write(ds.currmeasKey)
            return self._query_with_timeout(conn, ds.resultKey)

        raise ValueError(f"Unknown scope_id {self.scope_id!r}; expected '1', '2' or '3'.")

    def _query_with_timeout(self, conn: InstrumentConnection, command: str,
                            timeout_ms: int = 5000) -> float:
        """Run ``conn.query(command)`` with a temporary per-query timeout.

        Restores the previous timeout afterwards. Raises whatever the
        underlying connection raises on timeout (typically
        ``pyvisa.errors.VisaIOError``).
        """
        prev_timeout = getattr(conn, "timeout", None)
        try:
            try:
                conn.timeout = timeout_ms  # type: ignore[attr-defined]
            except AttributeError:
                pass
            return float(conn.query(command))
        finally:
            if prev_timeout is not None:
                try:
                    conn.timeout = prev_timeout  # type: ignore[attr-defined]
                except AttributeError:
                    pass
