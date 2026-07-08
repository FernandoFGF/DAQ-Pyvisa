"""
Arbitrary Waveform Generator acquisition adapter.

Hardware target: Siglent SDG2122X
(*IDN: Siglent Technologies,SDG2122X,SDG2XCAC6R0231,2.01.01.35R3B2).

SCPI command summary (one shot per parameter; the GUI sends
each line separately so a partial set is still useful):

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

The GUI in ``gui/tabs/arbgen.py`` collects the user-facing
parameters and calls into this module to send them.
"""

from __future__ import annotations

from typing import Mapping, Optional


# Channel-scope SCPI tokens. Both channels are exposed via the
# same commands by swapping the ``C1`` / ``C2`` prefix.
_SCOPE_CHANNEL = {"CH1": "C1", "CH2": "C2"}


def _scope(channel: str) -> str:
    """Return the ``C1`` / ``C2`` token for a GUI channel name."""
    return _SCOPE_CHANNEL.get(channel, "C1")


def _format_params_summary(params: Mapping[str, object]) -> str:
    """One-line summary of the parameter set, used by both the
    unit tests and the terminal log line."""
    return (f"channel={params.get('channel')} "
            f"wave={params.get('waveform_scpi')} "
            f"freq={params.get('frequency_hz')}Hz "
            f"amp={params.get('amplitude_vpp')}Vpp "
            f"Z={params.get('impedance')} "
            f"offset={params.get('offset_v')}V "
            f"phase={params.get('phase_deg')}deg")


def _coerce_float(value: object, default: float) -> float:
    """Best-effort string-to-float for SCPI command arguments.

    Falls back to ``default`` on any parse error so a typo in
    the GUI does not break the whole batch.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _scpi_apply_params(params: Mapping[str, object]) -> list[str]:
    """Build the list of SCPI lines for the Update button.

    One line per parameter; the GUI is free to ignore any line
    whose value is empty.
    """
    scope = _scope(str(params.get("channel", "CH1")))
    wave = str(params.get("waveform_scpi", "SINE"))
    freq = _coerce_float(params.get("frequency_hz"), 1000.0)
    amp = _coerce_float(params.get("amplitude_vpp"), 1.0)
    offset = _coerce_float(params.get("offset_v"), 0.0)
    phase = _coerce_float(params.get("phase_deg"), 0.0)
    width = _coerce_float(params.get("width_s"), 1e-6)
    lines = [
        f"{scope}:BSWV WVTP,{wave}",
        f"{scope}:BSWV FRQ,{freq}",
        f"{scope}:BSWV AMP,{amp}",
        f"{scope}:BSWV OFST,{offset}",
        f"{scope}:BSWV PHSE,{phase}",
    ]
    # Pulse width only makes sense for pulse waveforms but
    # Siglent accepts the command for the other types too, so
    # we send it unconditionally and let the scope ignore it.
    lines.append(f"{scope}:BSWV WIDTH,{width:.3E}")
    return lines


def _scpi_set_output(channel: str, on: bool) -> list[str]:
    """Build the SCPI line(s) for the on/off slide switch."""
    scope = _scope(channel)
    return [f"{scope}:OUTP {'ON' if on else 'OFF'}"]


def _scpi_set_load(channel: str, impedance: str) -> list[str]:
    """Build the SCPI line for the impedance selector."""
    scope = _scope(channel)
    # The GUI exposes "HiZ" / "50 Ohm". Siglent expects
    # ``HZ`` (high impedance) or ``50`` (50 ohm). We coerce
    # here so the GUI can stay user-friendly.
    if "50" in impedance:
        return [f"{scope}:OUTP LOAD,50"]
    return [f"{scope}:OUTP LOAD,HZ"]


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


def apply_arbgen_params(params: Mapping[str, object],
                        config: Optional[object] = None,
                        conn=None) -> None:
    """Send the Update-gated parameters to the AWG.

    When ``conn`` is provided we use it directly (the unit
    tests pass a ``FakeConnection``). Otherwise we open a
    fresh pyvisa session via the facade and let the helper
    functions issue the writes.
    """
    summary = _format_params_summary(params)
    lines = _scpi_apply_params(params)
    print(f"[ArbGen] apply {summary}")
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def set_arbgen_output(channel: str, on: bool,
                       config: Optional[object] = None,
                       conn=None) -> None:
    """Toggle the channel output on or off."""
    lines = _scpi_set_output(channel, on)
    print(f"[ArbGen] output channel={channel} on={on}")
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def set_arbgen_load(channel: str, impedance: str,
                     config: Optional[object] = None,
                     conn=None) -> None:
    """Set the channel output impedance (HiZ / 50 Ohm)."""
    lines = _scpi_set_load(channel, impedance)
    print(f"[ArbGen] load channel={channel} impedance={impedance}")
    for line in lines:
        print(f"[ArbGen]   {line}")
        _send(conn, line)


def set_arbgen_pulse_width(channel: str, width_s: float,
                            config: Optional[object] = None,
                            conn=None) -> None:
    """Set the pulse width (seconds) for the channel."""
    scope = _scope(channel)
    line = f"{scope}:BSWV WIDTH,{width_s:.3E}"
    print(f"[ArbGen] pulse width channel={channel} width={width_s:.3E}s")
    print(f"[ArbGen]   {line}")
    _send(conn, line)
