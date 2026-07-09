"""
Instrument connection abstraction for acquisition/.

The adapters in this package (IVAcquisition, SpectrumAcquisition,
WaveformAcquisition) do not depend on pyvisa directly. They take an
``InstrumentConnection`` in their ``set_connection`` method and call
``write`` / ``query`` / ``close`` on it. This keeps the SCPI logic
testable with the ``FakeConnection`` helper in tests/.

In production, ``open_pyvisa`` builds a real connection from a
config-defined address. Tests inject a ``FakeConnection`` instead.
"""

from __future__ import annotations

from typing import Optional, Protocol


class InstrumentConnection(Protocol):
    """Minimal interface a real pyvisa Resource or a fake both implement."""

    def write(self, command: str) -> None: ...
    def query(self, command: str) -> str: ...
    def close(self) -> None: ...
    def read_raw(self) -> bytes: ...


class _PyvisaAdapter:
    """Adapter that wraps a real pyvisa Resource to satisfy the protocol.

    The legacy code uses ``del smu.timeout`` to remove the timeout and
    later sets ``rta.timeout=20000`` on the scope. We expose ``timeout``
    as a settable attribute to keep that behaviour working.
    """

    def __init__(self, resource):
        self._resource = resource

    def write(self, command: str) -> None:
        self._resource.write(command)

    def query(self, command: str) -> str:
        return self._resource.query(command)

    def close(self) -> None:
        try:
            self._resource.close()
        except Exception:
            pass

    def read_raw(self) -> bytes:
        return self._resource.read_raw()

    @property
    def timeout(self):
        return getattr(self._resource, "timeout", None)

    @timeout.setter
    def timeout(self, value):
        try:
            self._resource.timeout = value
        except Exception:
            pass

    def __delattr__(self, name):
        # Legacy code does ``del smu.timeout`` to remove the timeout.
        if name == "timeout":
            try:
                self._resource.timeout = None
                return
            except Exception:
                pass
        super().__delattr__(name)


def _resolve_address(instrument_id: str, config=None) -> str:
    """Resolve an instrument_id like 'smu' or 'scope1' to a VISA address.

    Uses config.yaml (instruments.<id>.address) when available. Falls back
    to a deterministic placeholder so tests/devs get a clear error if the
    real address is missing.
    """
    if config is not None:
        try:
            instruments = config.get("instruments", {})
            if instrument_id in instruments:
                addr = instruments[instrument_id].get("address")
                if addr:
                    return addr
        except Exception:
            pass
    return f"TCPIP::missing::{instrument_id}::INSTR"


def open_pyvisa(instrument_id: str, config=None) -> InstrumentConnection:
    """Open a real pyvisa connection and return it as a protocol object.

    Imports pyvisa lazily so the package can be exercised (and tested)
    without pyvisa installed.
    """
    try:
        import pyvisa  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            f"pyvisa is not installed; cannot open real instrument "
            f"'{instrument_id}'. Use FakeConnection in tests."
        ) from e

    address = _resolve_address(instrument_id, config)
    rm = pyvisa.ResourceManager()
    resource = rm.open_resource(address)
    # 20 s default: long enough for a Keysight :WAV:DATA? (1.4 MB)
    # to finish even on a slow link, but short enough that a
    # completely unreachable scope fails fast. Matches the timeout
    # the waveform / spectrum adapters ask for, so reusing this
    # connection from the Connect tab does not need a second
    # timeout push.
    try:
        resource.timeout = 20000
    except Exception:
        pass
    return _PyvisaAdapter(resource)


def identify(instrument_id: str, conn: Optional[InstrumentConnection] = None,
             config=None) -> str:
    """Open (or use the provided) connection and return ``*IDN?`` response.

    If ``conn`` is provided, the existing connection is used (and not
    closed). Otherwise a fresh connection is opened and closed.
    """
    if conn is None:
        conn = open_pyvisa(instrument_id, config)
        try:
            return conn.query("*IDN?").strip()
        finally:
            conn.close()
    return conn.query("*IDN?").strip()


def connect_and_identify(instrument_id: str, config=None) -> tuple:
    """Open a connection to ``instrument_id`` and run ``*IDN?``.

    Returns ``(connection, identification_string)``. The caller is
    responsible for closing the connection (typically by storing the
    result on a manager and calling ``disconnect`` later).

    For tests, pass a ``FakeConnection`` via ``config['_fake_<id>']`` to
    avoid the real pyvisa dependency; this helper does not honour that
    today, but ``DAQGUIFunctions`` does (see tests).
    """
    conn = open_pyvisa(instrument_id, config)
    idn = conn.query("*IDN?").strip()
    return conn, idn
