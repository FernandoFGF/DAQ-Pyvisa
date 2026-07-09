"""
SCPI dialect registry for the Arbitrary Waveform Generator tab.

The AWG panel supports two hardware families, picked at runtime
from the *IDN? response of the connected instrument:

  * ``siglent``  - Siglent SDG2122X (and related SDG2xxx series).
                   ``*IDN?`` starts with ``Siglent Technologies``.
  * ``agilent``  - Agilent / Keysight 33600A series (e.g. 33612A).
                   ``*IDN?`` starts with ``Agilent Technologies`` or
                   ``Keysight Technologies``.

Each dialect maps a generic intent (set wave type, set frequency,
toggle output, ...) to the SCPI string the actual hardware
expects. The mapping is exposed as a flat dict so the GUI can
introspect it (e.g. to decide whether the phase field is
relevant, or to render a "Connected: <model>" indicator).

When the connected *IDN?* is unknown, we default to ``siglent``
to preserve the historical behaviour. The user can override
explicitly with :func:`dialect_for` if needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class ArbgenDialect:
    """The SCPI dialect of a single AWG family.

    All string fields may be either a literal command template
    (with ``{value}`` for the user-provided value) or a static
    string with no placeholder. ``formatters`` lets us coerce
    floats into the right unit / suffix per dialect (Siglent
    wants scientific notation, Agilent wants plain numbers).
    """

    key: str
    label: str
    # Wave-type tokens: GUI label -> SCPI token. Order matters for
    # the dropdown; keep it consistent across dialects so the UI
    # looks the same regardless of the connected AWG.
    wave_tokens: Dict[str, str]
    # Channel prefix used in commands. Siglent uses C1/C2,
    # Agilent uses SOUR1/SOUR2.
    channel_prefix: Callable[[str], str]
    # Per-dialect wave-type command template. ``{prefix}`` and
    # ``{token}`` are substituted at send time. Example:
    # Siglent  -> "{prefix}:BSWV WVTP,{token}"
    # Agilent  -> "{prefix}:FUNC {token}"
    wave_command: str
    # Output on/off templates.
    output_on: str
    output_off: str
    # Load (impedance) templates. Siglent has C1:OUTP LOAD,50
    # and C1:OUTP LOAD,HZ; Agilent has OUTP1:LOAD 50 and
    # OUTP1:LOAD INF.
    load_highz: str
    load_50: str
    # Phase is hidden when the active wave is a pulse train.
    # We still ship a command template in case the user sets
    # it; some Agilent firmware supports PULS phase, others do
    # not, so the GUI hides it by default for both.
    phase_supported: bool
    # Whether pulse width is hidden outside pulse-train mode.
    width_supported: bool


def _siglent_prefix(channel: str) -> str:
    """Siglent uses ``C1`` / ``C2`` as the channel token."""
    return {"CH1": "C1", "CH2": "C2"}.get(channel, "C1")


def _agilent_prefix(channel: str) -> str:
    """Agilent 33600A uses ``SOUR1`` / ``SOUR2`` as the channel token."""
    return {"CH1": "SOUR1", "CH2": "SOUR2"}.get(channel, "SOUR1")


SIGLENT = ArbgenDialect(
    key="siglent",
    label="Siglent SDG2122X",
    wave_tokens={
        "Sine": "SINE",
        "Square": "SQUARE",
        "Triangle": "RAMP",   # Siglent uses RAMP for triangle.
        "Pulse train": "PULSE",
    },
    channel_prefix=_siglent_prefix,
    # The legacy Siglent command set uses C1:BSWV WVTP,<wave> and
    # sends the rest of the parameters as separate C1:BSWV KEY,VALUE
    # writes (see _scpi_apply_params in arbgen_acquisition.py).
    wave_command="{prefix}:BSWV WVTP,{token}",
    output_on="{prefix}:OUTP ON",
    output_off="{prefix}:OUTP OFF",
    load_highz="{prefix}:OUTP LOAD,HZ",
    load_50="{prefix}:OUTP LOAD,50",
    phase_supported=True,
    width_supported=True,
)


AGILENT = ArbgenDialect(
    key="agilent",
    label="Keysight / Agilent 33612A",
    # Agilent does not expose a Triangle option in the 33600A
    # family, so the dropdown omits it for the Agilent dialect.
    wave_tokens={
        "Sine": "SIN",
        "Square": "SQU",
        "Pulse train": "PULS",
        "Noise": "NOIS",
        "DC": "DC",
        "Arb": "ARB",
    },
    channel_prefix=_agilent_prefix,
    wave_command="{prefix}:FUNC {token}",
    output_on="OUTP{idx} ON",
    output_off="OUTP{idx} OFF",
    load_highz="OUTP{idx}:LOAD INF",
    load_50="OUTP{idx}:LOAD 50",
    phase_supported=True,
    width_supported=True,
)


# ``{idx}`` is the per-channel numeric index (1 / 2). Agilent
# uses a separate command family (``OUTP1`` / ``OUTP2``) for the
# output switch, distinct from the ``SOUR1`` / ``SOUR2`` prefix
# used for waveform parameters. The formatter below resolves
# ``{idx}`` from the channel the user is working on.
def _format(template: str, channel: str, **kwargs) -> str:
    idx = {"CH1": "1", "CH2": "2"}.get(channel, "1")
    return template.format(idx=idx, channel=channel, **kwargs)


# Public registry.
DIALECTS: Dict[str, ArbgenDialect] = {
    "siglent": SIGLENT,
    "agilent": AGILENT,
}


# Manufacturer detection from *IDN?* responses. The 33600A
# series identifies as ``Agilent Technologies`` in the older
# firmware and as ``Keysight Technologies`` in the newer
# firmware; both families use the same SCPI dialect, so we map
# either manufacturer to the same dialect.
_MANUFACTURER_PATTERNS = [
    (re.compile(r"^Agilent\s+Technologies", re.IGNORECASE), "agilent"),
    (re.compile(r"^Keysight\s+Technologies", re.IGNORECASE), "agilent"),
    (re.compile(r"^Siglent\s+Technologies", re.IGNORECASE), "siglent"),
]


def dialect_for_idn(idn: str) -> Optional[ArbgenDialect]:
    """Return the dialect matching an ``*IDN?`` response.

    ``None`` is returned when the manufacturer is not one of
    the supported families. The caller is expected to fall
    back to a default in that case.
    """
    if not idn:
        return None
    head = idn.split(",", 1)[0].strip()
    for pattern, key in _MANUFACTURER_PATTERNS:
        if pattern.match(head):
            return DIALECTS[key]
    return None


def wave_labels_for(dialect: ArbgenDialect) -> List[str]:
    """Return the dropdown labels in the order they should appear."""
    return list(dialect.wave_tokens.keys())


def wave_token_for(dialect: ArbgenDialect, label: str) -> str:
    """Resolve a dropdown label to its SCPI token for ``dialect``."""
    return dialect.wave_tokens.get(label, "SIN" if dialect.key == "agilent" else "SINE")
