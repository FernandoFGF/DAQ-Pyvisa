"""
IV acquisition adapter.

Replicates the SCPI logic of ``daq_gui_func.start_iv`` (the option=="SMU"
branch, lines 51-90) without touching the GUI. The adapter takes a
``v_start``, ``v_stop`` and ``v_step``, configures the SMU for a stepped
voltage sweep, runs it and returns the (voltage, current) arrays.

The SMU is opened through ``InstrumentConnection`` so tests can inject a
``FakeConnection`` (see ``tests/fake_connection.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from acquisition.connection import InstrumentConnection, open_pyvisa
from acquisition.save import save_iv_text


@dataclass
class IVResult:
    voltage: np.ndarray
    current: np.ndarray
    points: int


class IVAcquisition:
    def __init__(self, smu_id: str = "smu", v_start: float = 1.0,
                 v_stop: float = -40.0, v_step: float = 0.05,
                 config=None) -> None:
        self.smu_id = smu_id
        self.v_start = float(v_start)
        self.v_stop = float(v_stop)
        self.v_step = float(v_step)
        self.config = config
        self._conn: Optional[InstrumentConnection] = None

    def set_connection(self, conn: InstrumentConnection) -> None:
        """Inject a connection (used by tests)."""
        self._conn = conn

    def open(self) -> None:
        if self._conn is None:
            self._conn = open_pyvisa(self.smu_id, self.config)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "IVAcquisition":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(self) -> IVResult:
        """Execute the SMU voltage sweep and return the IVResult."""
        self.open()
        conn = self._conn
        assert conn is not None

        # Legacy: ``del smu.timeout`` clears the VISA timeout. The adapter
        # handles ``__delattr__("timeout")`` by setting it to None.
        try:
            del conn.timeout  # type: ignore[attr-defined]
        except AttributeError:
            pass

        # Reset + configure for stepped voltage sweep (legacy sequence)
        conn.write("*RST")
        conn.write(":SOUR:FUNC:MODE VOLT")
        conn.write(":SOUR:SWE:MODE SWE")
        conn.write(":SOUR:SWE:STA SING")
        conn.write(":SOUR:SWE:SPAC LIN")
        conn.write(f":SOUR:VOLT:STAR {self.v_start}")
        conn.write(f":SOUR:VOLT:STOP {self.v_stop}")
        points = int(abs(self.v_start - self.v_stop) / self.v_step)
        conn.write(f":SOUR:VOLT:POIN {points}")

        # Auto-range current measurement
        conn.write(":SENS:CURR:RSEN AUTO")
        conn.write(":SENS:CURR:RANG:AUTO ON")
        conn.write(":SENS:FUNC 'CURR'")
        # Trigger: count == points
        conn.write(":TRIG:SOUR INT")
        conn.write(f":TRIG:COUN {points}")

        # Output on, init, wait
        conn.write(":OUTP ON")
        conn.write(":INIT")
        self._wait_for_complete(conn)

        # Read back
        i_raw = conn.query(":FETC:ARR:CURR?")
        i_values = [s for s in i_raw.replace("\n", "").split(",") if s]
        v_raw = conn.query(":FETC:ARR:VOLT?")
        v_values = [s for s in v_raw.replace("\n", "").split(",") if s]

        # Output off
        conn.write(":OUTP OFF")

        return IVResult(
            voltage=np.array([float(v) for v in v_values], dtype=float),
            current=np.array([float(i) for i in i_values], dtype=float),
            points=points,
        )

    @staticmethod
    def _wait_for_complete(conn: InstrumentConnection) -> None:
        """Poll ``*OPC?`` until the SMU returns '1'.

        Replaces ``lab_module.waiting``. Bounded to a generous number of
        iterations to avoid hanging forever in tests.
        """
        for _ in range(100_000):
            if conn.query("*OPC?").strip() == "1":
                return

    def save(self, path: str, v_values: Sequence[float], i_values: Sequence[float]) -> None:
        save_iv_text(path, v_values, i_values)
