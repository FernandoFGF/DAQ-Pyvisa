"""
IV acquisition adapter.

Replicates the SCPI logic of ``daq_gui_func.start_iv`` (the
option == "SMU" branch, lines 51-90) without touching the GUI.
The adapter takes a ``v_start``, ``v_stop`` and ``v_step``,
configures the SMU for a stepped voltage sweep, runs it and
returns the (voltage, current) arrays.

The SMU is opened through ``InstrumentConnection`` so tests can
inject a ``FakeConnection`` (see ``tests/fake_connection.py``).

Command sequence (matches the legacy line by line, using the
tokens from ``acquisition.scpi_dictionary`` which is the modern
home of the old ``dictionary_SCPI.py``):

  *RST
  :SOUR:VOLT:MODE VOLT
  :SOUR:VOLT:MODE SWE
  :SOUR:SWE:STA SING
  :SOUR:SWE:SPAC LIN
  :SOUR:VOLT:STAR <v_start>
  :SOUR:VOLT:STOP <v_stop>
  :SOUR:VOLT:POIN <points>
  :sens:func "curr"
  :sens:curr:nplc 0.1
  :sens:curr:prot 0.01
  :trig:sour aint
  :trig:coun <points>
  :outp on
  :init (@1)
  <block on *OPC?>
  :fetc:arr:curr? (@1)
  :fetc:arr:volt? (@1)
  :outp off

The (@1) channel selector is critical: the SMU 2470 returns a
single value or an error when the channel specifier is missing,
so the legacy code always included it. We do the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from acquisition import scpi_dictionary as ds
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
                 config=None, channel: int = 1) -> None:
        self.smu_id = smu_id
        self.v_start = float(v_start)
        self.v_stop = float(v_stop)
        self.v_step = float(v_step)
        self.config = config
        # The Keithley 2470 has two channels; the user picks
        # which one to drive from the IV tab. The number is
        # substituted into the ``(@N)`` token of the :init and
        # :FETCh commands. Clamped to 1..2 because the SMU
        # firmware rejects anything outside that range.
        self.channel = max(1, min(2, int(channel)))
        self._conn: Optional[InstrumentConnection] = None
        # When ``set_connection`` injects an externally-owned
        # connection (the one the Connect card is holding) we must
        # NOT close it on ``close()``; the GUI owns the lifetime and
        # will close it itself. When we opened the connection
        # ourselves, ``close()`` is the right place to release it.
        self._owns_connection: bool = False

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
            self._conn = open_pyvisa(self.smu_id, self.config)
            self._owns_connection = True

    def close(self) -> None:
        if self._conn is not None and self._owns_connection:
            self._conn.close()
        self._conn = None
        self._owns_connection = False

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

        # Legacy: ``del smu.timeout`` clears the VISA timeout. The
        # adapter handles ``__delattr__("timeout")`` by setting the
        # resource timeout to None.
        try:
            del conn.timeout  # type: ignore[attr-defined]
        except AttributeError:
            pass

        # Reset + configure for stepped voltage sweep. The legacy
        # command set lives in ``acquisition.scpi_dictionary`` (formerly
        # ``old/dictionary_SCPI.py``); we use those tokens verbatim
        # so any future update to the dictionary automatically
        # propagates to the new adapter.
        conn.write(ds.rst)
        conn.write(ds.voltMode)
        conn.write(ds.sweepMode)
        conn.write(ds.sweepSing)
        conn.write(ds.sweepLin)
        conn.write(f":SOUR:VOLT:STAR {self.v_start}")
        conn.write(f":SOUR:VOLT:STOP {self.v_stop}")
        # The legacy used int() and assumed v_step divides the span
        # exactly. We do the same so the SMU-side POIN matches the
        # TRIG:COUN we send next.
        points = int(abs(self.v_start - self.v_stop) / self.v_step)
        conn.write(f":SOUR:VOLT:POIN {points}")
        # Auto-range current measurement, NPLC 0.1, 10 mA protection.
        # The legacy 2470 setup that produced the curves the user
        # signed off on.
        conn.write(ds.smuAuto1)
        conn.write(ds.smuAuto2)
        conn.write(ds.smuAuto3)
        # Trigger: arm-and-trigger by the SMU's own sequencer
        # (``aint``), fire ``points`` times.
        conn.write(ds.smuTrig)
        conn.write(f":trig:coun {points}")
        # Output on, init, wait for completion.
        conn.write(ds.smuOn)
        # The :init and :FETCh commands need the channel selector
        # (``(@N)``) so the SMU knows which channel to drive / read.
        # The legacy code always used 1; we now substitute the user
        # selection from the IV tab.
        ch = self.channel
        conn.write(f":init (@{ch})")
        self._wait_for_complete(conn)
        # Read back both arrays from the selected channel. The
        # ``(@N)`` is non-optional on the 2470: without it the SMU
        # errors with ``-221,Settings conflict`` and returns a single
        # value instead of the full sweep, which is what produced the
        # broken curve the user reported.
        i_result = conn.query(f":fetc:arr:curr? (@{ch})")
        v_result = conn.query(f":fetc:arr:volt? (@{ch})")
        # Output off.
        conn.write(ds.smuOff)

        # Parse ``-1.23E-04,-1.24E-04,...`` into float lists. The
        # legacy used ``split(",")`` then rstripped the trailing
        # newline; we do the same and then drop any empty fragments
        # so a stray trailing comma does not raise on float().
        i_values = [s for s in i_result.replace("\n", "").split(",") if s]
        v_values = [s for s in v_result.replace("\n", "").split(",") if s]
        # Defensive: when the SMU returns fewer values than we asked
        # for (e.g. transient comms error), pad with NaN so the GUI
        # plot still renders instead of misaligning two arrays of
        # different lengths. Pad up to the longer of the two so the
        # two arrays always have the same length; if both are
        # shorter than the configured ``points`` we still leave
        # them at the longer length so the curves overlay.
        n_i, n_v = len(i_values), len(v_values)
        if n_i != n_v:
            target = max(n_i, n_v, points)
            print(f"[IV] SMU returned {n_i} current and {n_v} voltage "
                  f"values (expected {points}); padding with NaN to {target}.")
            i_values = i_values + ["nan"] * (target - n_i)
            v_values = v_values + ["nan"] * (target - n_v)
        return IVResult(
            voltage=np.array([float(v) for v in v_values], dtype=float),
            current=np.array([float(i) for i in i_values], dtype=float),
            points=points,
        )

    @staticmethod
    def _wait_for_complete(conn: InstrumentConnection) -> None:
        """Poll ``*OPC?`` until the SMU returns ``'1'``.

        Replaces ``lab_module.waiting``. Bounded to a generous
        number of iterations so a real hardware hang cannot lock
        the worker thread forever, and so unit tests do not run
        away.
        """
        for _ in range(100_000):
            if conn.query("*OPC?").strip() == "1":
                return

    def save(self, path: str, v_values: Sequence[float], i_values: Sequence[float]) -> None:
        save_iv_text(path, v_values, i_values)
