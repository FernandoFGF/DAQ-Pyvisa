"""
Spectrum (charge histogram) acquisition adapter.

Mirrors ``daq_gui_func.start_spectrum`` exactly, including the three
oscilloscope dialects the legacy supports:

  * scope 1 (RTA, R&S RTA4000 series): two ``MEAS:RES:ACT?`` queries
    at the two cursor positions, charge = p_1 - p_2.
  * scope 2 (RTO, R&S RTO2000 series): single ``MEAS1:RES:ACT?`` query.
  * scope 3 (KEY, Keysight): ``headerOff`` + ``MEAS:RES?`` query.

The adapter also calls back every 100 samples so a GUI can redraw the
histogram, matching the legacy behaviour of ``self.canvas.draw()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from acquisition.connection import InstrumentConnection, open_pyvisa


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

    def set_connection(self, conn: InstrumentConnection) -> None:
        self._conn = conn

    def open(self) -> None:
        if self._conn is None:
            target = self.instrument_id or f"scope{self.scope_id}"
            self._conn = open_pyvisa(target, self.config)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
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

        # Legacy: ``del rta.timeout`` to clear the timeout.
        try:
            del conn.timeout  # type: ignore[attr-defined]
        except AttributeError:
            pass

        x_values: List[float] = []
        for i in range(1, self.num_datos + 1):
            r_r = self._read_one(conn)
            x_values.append(r_r)

            if progress_callback is not None and i % 100 == 0:
                progress_callback(np.array(x_values, dtype=float))

        return SpectrumResult(
            data=np.array(x_values, dtype=float),
            scope=self.scope_id,
            channel=self.channel,
            num_datos=self.num_datos,
        )

    def _read_one(self, conn: InstrumentConnection) -> float:
        """Read a single charge sample using the scope's dialect."""
        if self.scope_id == SCOPE_RTA:
            conn.write("FORM BIN")
            conn.write(f":MEAS:RES:ACT {self._cursor_channel()}")
            p_1 = float(conn.query(":MEAS:RES:ACT? P1"))
            p_2 = float(conn.query(":MEAS:RES:ACT? P2"))
            return p_1 - p_2

        if self.scope_id == SCOPE_RTO:
            conn.write("FORM BIN")
            conn.write(f":MEAS:RES:ACT {self._cursor_channel()}")
            return float(conn.query("MEAS1:RES:ACT?"))

        if self.scope_id == SCOPE_KEY:
            conn.write("FORM ASC")
            conn.write(f":MEAS:RES {self._cursor_channel()}")
            return float(conn.query(":MEAS:RES?"))

        raise ValueError(f"Unknown scope_id {self.scope_id!r}; expected '1', '2' or '3'.")

    def _cursor_channel(self) -> str:
        """Translate the legacy 'MA1'..'MA4' channel id into the scope SCPI."""
        if self.channel.startswith("MA"):
            return self.channel
        return f"MA{self.channel}"
