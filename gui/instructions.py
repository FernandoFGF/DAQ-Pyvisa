"""
Per-scope, per-function instructions for the DAQ app.

The instructions live in ``instructions.json`` at the project root.
Each top-level key is a function name (``"spectrum"``,
``"waveform"``, ``"iv"``); each sub-key is a scope friendly name
normalised to lowercase (``"rta"``, ``"rto"``, ``"keysight"``).
The values are lists of plain-text lines shown in a floating
window when the user clicks the "Instructions" button on the
right option frame.
"""

from __future__ import annotations

import json
import os
from typing import List


# Map the tab name shown on the GUI ("Spectrum", "IV Curves",
# "Waveform") to the JSON key in instructions.json.
_FUNCTION_MAP = {
    "Spectrum": "spectrum",
    "Waveform": "waveform",
    "IV Curves": "iv",
}

# Map the friendly scope name (as shown on the Connect card and
# the scope label on each tab) to the JSON key.
_SCOPE_MAP = {
    "RTA": "rta",
    "RTO": "rto",
    "KEY": "keysight",
}


def _project_root() -> str:
    """Locate the directory that holds ``instructions.json``.

    The file lives at the project root (``gui/instructions.py``
    sits in ``gui/`` so its parent is the project root).
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_raw() -> dict:
    """Read ``instructions.json`` from disk. Returns ``{}`` on any
    error so the GUI never crashes because of a malformed file."""
    path = os.path.join(_project_root(), "instructions.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_instructions(function: str, scope: str) -> List[str]:
    """Return the instruction lines for ``(function, scope)``.

    Both arguments are normalised against the friendly names used
    on the GUI. Unknown combinations return ``["none"]`` so the
    user always sees something rather than an empty window, which
    matches the agreed UX.
    """
    fn_key = _FUNCTION_MAP.get(function, function.strip().lower())
    scope_key = _SCOPE_MAP.get(scope, scope.strip().lower())
    raw = _load_raw()
    lines = raw.get(fn_key, {}).get(scope_key)
    if not lines:
        return ["none"]
    return [str(line) for line in lines]
