"""
Arbitrary Waveform Generator acquisition adapter.

Supports two hardware families, picked at runtime from the
``*IDN?`` response of the connected instrument:

  * Siglent SDG2122X  (dialect ``siglent``)
  * Agilent / Keysight 33612A  (dialect ``agilent``)

SCPI command summary
===================

Siglent SDG2122X
----------------

  +----------------------------+-----------------------------------+
  | Function                   | SCPI                              |
  +----------------------------+-----------------------------------+
  | Wave type                  | C1:BSWV WVTP,<SINE|SQUARE|RAMP|    |
  |                            |       PULSE>                       |
  | Frequency                  | C1:BSWV FRQ,<Hz>                  |
  | Amplitude (Vpp)            | C1:BSWV AMP,<Vpp>                  |
  | Offset                     | C1:BSWV OFST,<V>                  |
  | Phase                      | C1:BSWV PHSE,<deg>                |
  | Pulse width                | C1:BSWV WIDTH,<seconds>           |
  | Output on/off              | C1:OUTP ON  /  C1:OUTP OFF        |
  | Impedance                  | C1:OUTP LOAD,<50|HZ>               |
  +----------------------------+-----------------------------------+

Agilent / Keysight 33612A
-------------------------

  +----------------------------+-----------------------------------+
  | Function                   | SCPI                              |
  +----------------------------+-----------------------------------+
  | Wave type                  | SOUR1:FUNC <SIN|SQU|RAMP|PULS|     |
  |                            |          NOIS|DC|ARB>              |
  | Frequency                  | SOUR1:FREQ <Hz>                   |
  | Amplitude (Vpp)            | SOUR1:VOLT <Vpp>                  |
  | Offset                     | SOUR1:VOLT:OFFS <V>               |
  | Phase                      | SOUR1:PHAS <deg>                  |
  | Pulse width                | SOUR1:FUNC:PULS:WIDT <seconds>    |
  | Output on/off              | OUTP1 ON  /  OUTP1 OFF            |
  | Impedance                  | OUTP1:LOAD <50|INF>               |
  +----------------------------+-----------------------------------+

Both families accept one command per parameter; the GUI sends
each line separately so a partial set is still useful.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from acquisition.arbgen_dialects import (
    AGILENT,
    DIALECTS,
    SIGLENT,
    ArbgenDialect,
    dialect_for_idn,
    wave_token_for,
)


# Default dialect when the user has not connected yet. Keeps the
# historical Siglent behaviour so the rest of the app does not
# need to special-case the unconnected state.
DEFAULT_DIALECT: ArbgenDialect = SIGLENT


@dataclass
class _Channel:
    """Per-channel state cached by the adapter.

    The adapter does not really need to cache anything (the
    scope is the source of truth), but holding the last-sent
    pulse width lets the focus-out handler send only when the
    value actually changed. Optional, so the dataclass works
    with simple defaults.
    """

    last_pulse_width: Optional[float] = None


class _ChannelState:
    """Small registry that hands out a ``_Channel`` per GUI channel."""

    def __init__(self) -> None:
        self._by_channel: dict = {}

    def get(self, channel: str) -> _Channel:
        if channel not in self._by_channel:
            self._by_channel[channel] = _Channel()
        return self._by_channel[channel]


_CHANNEL_STATE = _ChannelState()


def _coerce_float(value: object, default: float) -> float:
    """Best-effort string-to-float for SCPI command arguments.

    Falls back to ``default`` on any parse error so a typo in
    the GUI does not break the whole batch.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_siglent_params(dialect: ArbgenDialect, params: Mapping[str, object],
                           wave_token: str) -> list[str]:
    """Build SCPI lines for the Siglent dialect.

    Siglent wants the wave type and the numeric parameters
    sent as separate ``C1:BSWV KEY,VALUE`` writes, so we emit
    one line per parameter (the GUI is free to ignore any
    line whose value is empty).
    """
    prefix = dialect.channel_prefix(str(params.get("channel", "CH1")))
    freq = _coerce_float(params.get("frequency_hz"), 1000.0)
    amp = _coerce_float(params.get("amplitude_vpp"), 1.0)
    offset = _coerce_float(params.get("offset_v"), 0.0)
    phase = _coerce_float(params.get("phase_deg"), 0.0)
    width = _coerce_float(params.get("width_s"), 1e-6)
    lines = [
        f"{prefix}:BSWV WVTP,{wave_token}",
        f"{prefix}:BSWV FRQ,{freq}",
        f"{prefix}:BSWV AMP,{amp}",
        f"{prefix}:BSWV OFST,{offset}",
        f"{prefix}:BSWV PHSE,{phase}",
    ]
    # Pulse width only makes sense for pulse waveforms but
    # Siglent accepts the command for the other types too, so
    # we send it unconditionally and let the scope ignore it.
    lines.append(f"{prefix}:BSWV WIDTH,{width:.3E}")
    return lines


def _format_agilent_params(dialect: ArbgenDialect, params: Mapping[str, object],
                           wave_token: str) -> list[str]:
    """Build SCPI lines for the Agilent 33612A dialect.

    Agilent wants a single ``SOUR1:FUNC <token>`` write and
    then one ``SOUR1:KEY VALUE`` line per numeric parameter.
    Phase is hidden in the GUI for pulse trains (where it
    would be ignored by the scope), but we still emit it here
    if the user managed to set a value; the worst the scope
    does is reply with a setting conflict, which the
    connection layer logs as an error and the rest of the
    batch can still proceed.
    """
    prefix = dialect.channel_prefix(str(params.get("channel", "CH1")))
    channel = str(params.get("channel", "CH1"))
    freq = _coerce_float(params.get("frequency_hz"), 1000.0)
    amp = _coerce_float(params.get("amplitude_vpp"), 1.0)
    offset = _coerce_float(params.get("offset_v"), 0.0)
    phase = _coerce_float(params.get("phase_deg"), 0.0)
    width = _coerce_float(params.get("width_s"), 1e-6)
    lines = [
        dialect.wave_command.format(prefix=prefix, token=wave_token),
        f"{prefix}:FREQ {freq}",
        f"{prefix}:VOLT {amp}",
        f"{prefix}:VOLT:OFFS {offset}",
        f"{prefix}:PHAS {phase}",
    ]
    if wave_token == "PULS":
        lines.append(f"{prefix}:FUNC:PULS:WIDT {width:.3E}")
    return lines


def _format_params(dialect: ArbgenDialect, params: Mapping[str, object],
                   wave_token: str) -> list[str]:
    """Pick the right formatter for ``dialect``."""
    if dialect.key == "agilent":
        return _format_agilent_params(dialect, params, wave_token)
    return _format_siglent_params(dialect, params, wave_token)


def _format_output(dialect: ArbgenDialect, channel: str, on: bool) -> list[str]:
    """Build the SCPI line for the on/off slide switch."""
    if dialect.key == "agilent":
        idx = {"CH1": "1", "CH2": "2"}.get(channel, "1")
        template = dialect.output_on if on else dialect.output_off
        return [template.format(idx=idx, channel=channel)]
    prefix = dialect.channel_prefix(channel)
    template = dialect.output_on if on else dialect.output_off
    return [template.format(prefix=prefix, channel=channel)]


def _format_load(dialect: ArbgenDialect, channel: str, impedance: str) -> list[str]:
    """Build the SCPI line for the impedance selector.

    Siglent accepts ``50`` or ``HZ``; Agilent accepts ``50``
    or ``INF``. The GUI exposes ``HiZ`` / ``50 Ohm`` so we
    coerce the label here.
    """
    if dialect.key == "agilent":
        idx = {"CH1": "1", "CH2": "2"}.get(channel, "1")
        template = dialect.load_50 if "50" in impedance else dialect.load_highz
        return [template.format(idx=idx, channel=channel)]
    prefix = dialect.channel_prefix(channel)
    template = dialect.load_50 if "50" in impedance else dialect.load_highz
    return [template.format(prefix=prefix, channel=channel)]


def _format_pulse_width(dialect: ArbgenDialect, channel: str,
                        width_s: float) -> list[str]:
    """Build the SCPI line for the pulse-width input."""
    if dialect.key == "agilent":
        prefix = dialect.channel_prefix(channel)
        return [f"{prefix}:FUNC:PULS:WIDT {width_s:.3E}"]
    prefix = dialect.channel_prefix(channel)
    return [f"{prefix}:BSWV WIDTH,{width_s:.3E}"]


def _send(conn, line: str) -> None:
    """Send a single SCPI line over the live connection.

    The connection protocol (``acquisition.connection.InstrumentConnection``)
    exposes ``write``; we route through that so the adapter is
    unit-testable with a ``FakeConnection``.
    """
    if conn is None:
        print(f"[ArbGen]   (no conn, not sent: {line})")
        return
    try:
        conn.write(line)
        print(f"[ArbGen]   sent: {line}")
    except Exception as e:
        print(f"[ArbGen]   write failed: {line} -> {e}")


def detect_dialect(conn, fallback: ArbgenDialect = DEFAULT_DIALECT) -> ArbgenDialect:
    """Return the AWG dialect detected from ``conn``'s ``*IDN?``.

    Falls back to ``fallback`` (Siglent by default) if the
    query fails or the manufacturer is unknown. Safe to call
    before a connection is open: returns ``fallback``.
    """
    if conn is None:
        return fallback
    try:
        idn = conn.query("*IDN?")
    except Exception:
        return fallback
    return dialect_for_idn(idn) or fallback


def identify_awg(conn) -> str:
    """Return the ``*IDN?`` response stripped of whitespace.

    Returns an empty string when the query fails. The GUI uses
    this to populate the "Connected:" indicator and the
    instructions window.
    """
    if conn is None:
        return ""
    try:
        return str(conn.query("*IDN?")).strip()
    except Exception:
        return ""


def apply_arbgen_params(params: Mapping[str, object],
                        config: Optional[object] = None,
                        conn=None,
                        dialect: Optional[ArbgenDialect] = None) -> None:
    """Send the Update-gated parameters to the AWG.

    When ``conn`` is provided we use it directly (the unit
    tests pass a ``FakeConnection``). Otherwise we open a
    fresh pyvisa session via the facade and let the helper
    functions issue the writes.

    ``dialect`` overrides the auto-detection (used by the
    GUI to keep the same dialect between commands; auto
    detection would otherwise re-query ``*IDN?`` on every
    click).
    """
    d = dialect or detect_dialect(conn)
    label = str(params.get("waveform_label", ""))
    wave_token = wave_token_for(d, label)
    summary = (
        f"channel={params.get('channel')} wave={wave_token} "
        f"freq={params.get('frequency_hz')}Hz "
        f"amp={params.get('amplitude_vpp')}Vpp "
        f"Z={params.get('impedance')} "
        f"offset={params.get('offset_v')}V "
        f"phase={params.get('phase_deg')}deg "
        f"width={params.get('width_s')}s "
        f"dialect={d.key}"
    )
    print(f"[ArbGen] apply {summary}")
    lines = _format_params(d, params, wave_token)
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def set_arbgen_output(channel: str, on: bool,
                       config: Optional[object] = None,
                       conn=None,
                       dialect: Optional[ArbgenDialect] = None) -> None:
    """Toggle the channel output on or off."""
    d = dialect or detect_dialect(conn)
    lines = _format_output(d, channel, on)
    print(f"[ArbGen] output channel={channel} on={on} dialect={d.key}")
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def set_arbgen_load(channel: str, impedance: str,
                     config: Optional[object] = None,
                     conn=None,
                     dialect: Optional[ArbgenDialect] = None) -> None:
    """Set the channel output impedance (HiZ / 50 Ohm)."""
    d = dialect or detect_dialect(conn)
    lines = _format_load(d, channel, impedance)
    print(f"[ArbGen] load channel={channel} impedance={impedance} dialect={d.key}")
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def set_arbgen_pulse_width(channel: str, width_s: float,
                            config: Optional[object] = None,
                            conn=None,
                            dialect: Optional[ArbgenDialect] = None) -> None:
    """Set the pulse width (seconds) for the channel.

    The change is only sent when the value actually differs
    from the last-sent value, so the focus-out handler does
    not spam the scope on every focus change. The cache is
    process-global; tests that need to exercise the "first
    time" path can call :func:`reset_pulse_width_cache`.
    """
    d = dialect or detect_dialect(conn)
    state = _CHANNEL_STATE.get(channel)
    if state.last_pulse_width is not None and abs(state.last_pulse_width - width_s) < 1e-15:
        return
    state.last_pulse_width = width_s
    lines = _format_pulse_width(d, channel, width_s)
    print(f"[ArbGen] pulse width channel={channel} width={width_s:.3E}s dialect={d.key}")
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def reset_pulse_width_cache() -> None:
    """Forget the last-sent pulse width for every channel.

    Test helper: lets a test that wants to send the same
    value twice (e.g. to confirm the dedup path) reset the
    dedup cache between runs.
    """
    for state in _CHANNEL_STATE._by_channel.values():
        state.last_pulse_width = None


__all__ = [
    "AGILENT",
    "DEFAULT_DIALECT",
    "DIALECTS",
    "SIGLENT",
    "ArbgenDialect",
    "apply_arbgen_params",
    "detect_dialect",
    "dialect_for_idn",
    "identify_awg",
    "reset_pulse_width_cache",
    "set_arbgen_load",
    "set_arbgen_output",
    "set_arbgen_pulse_width",
    "wave_labels_for",
    "wave_token_for",
]

# Re-export the dialect helpers from arbgen_dialects so callers
# (the GUI, the tests) can import everything from a single module.
# Imports at module bottom would not work because the dialect
# module imports from this one in turn.
from acquisition.arbgen_dialects import (  # noqa: E402, F401
    wave_labels_for,
    wave_token_for,
)
