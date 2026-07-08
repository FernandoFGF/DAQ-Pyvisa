"""
Arbitrary Waveform Generator acquisition adapter.

Hardware target: Siglent SDG2122X
(*IDN: ``Siglent Technologies,SDG2122X,SDG2XCAC6R0231,2.01.01.35R3B2``).

The GUI in ``gui/tabs/arbgen.py`` collects the user-facing
parameters (channel, wave type, frequency, amplitude,
impedance, offset, phase) and calls into this module to send
them to the instrument. Two entry points are exposed:

  * ``apply_arbgen_params(params, config=None)``
      Sends the six parameters that are gated by the Update
      button (everything except on/off).

  * ``set_arbgen_output(channel, on, config=None)``
      Toggles the channel output on or off. Fires immediately
      when the on/off slide switch moves.

For now both functions are stubs that print the SCPI command
they would send. The user is going to feed us the exact
Siglent command syntax in a follow-up; until then the GUI
prints the parameter set so we can iterate on the UX.
"""

from __future__ import annotations

from typing import Mapping, Optional


def _resolve_config_instrument_id(channel: str) -> str:
    """Map the GUI channel (CH1 / CH2) to the config.yaml key
    used by ``acquisition.connection.open_pyvisa``.

    Today the config only exposes a single ``arbGen`` entry.
    When the user adds a second generator to config.yaml we
    will look up the right address here.
    """
    return "arbGen"


def _format_params_summary(params: Mapping[str, object]) -> str:
    """One-line summary of the parameter set, used by both the
    stub SCPI print and the unit tests."""
    return (f"channel={params.get('channel')} "
            f"wave={params.get('waveform_scpi')} "
            f"freq={params.get('frequency_hz')}Hz "
            f"amp={params.get('amplitude_vpp')}Vpp "
            f"Z={params.get('impedance')} "
            f"offset={params.get('offset_v')}V "
            f"phase={params.get('phase_deg')}deg")


def apply_arbgen_params(params: Mapping[str, object],
                        config: Optional[object] = None) -> None:
    """Send the six Update-gated parameters to the AWG.

    Currently a stub: prints the SCPI command we would send.
    The real implementation lands here once the user provides
    the Siglent command syntax.
    """
    summary = _format_params_summary(params)
    # Real SCPI will be inserted by the user in a follow-up
    # (e.g. ``C1:BSWV WVTP,SINE,FRQ,1000,AMP,1.0,OFST,0.0,PHSE,0``).
    print(f"[ArbGen] SCPI(apply) -> {summary}")


def set_arbgen_output(channel: str, on: bool,
                       config: Optional[object] = None) -> None:
    """Toggle the channel output on or off.

    Currently a stub: prints the SCPI command we would send.
    """
    state = "ON" if on else "OFF"
    print(f"[ArbGen] SCPI(output) -> channel={channel} state={state}")
