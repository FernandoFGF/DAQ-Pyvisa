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
# "Waveform") to the JSON key in instructions.json. Only the
# tabs that have an instructions button get an entry; the
# others fall through to "none".
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
    error so the GUI never crashes because of a malformed file.

    Uses ``strict=False`` so the user can paste instructions with
    real line breaks inside a JSON string (e.g. RTA scope recipes)
    without us having to escape them.
    """
    path = os.path.join(_project_root(), "instructions.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f, strict=False)
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


def build_instructions_icon(parent, function: str, app=None):
    """Build a small circular "i" info button for the given tab.

    The button reads ``self.get_active_scope()`` from the bound
    application to figure out which scope is currently connected
    and shows the corresponding instructions in a movable
    non-modal ``CTkToplevel`` window.

    ``app`` is the application instance; when ``None`` the button
    tries to walk up the parent widget tree to find a method named
    ``get_active_scope`` (this is how the spectrum / waveform
    tabs hook it up).
    """
    import customtkinter as ctk

    btn = ctk.CTkButton(
        parent,
        text="i",
        width=26,
        height=26,
        corner_radius=13,
        font=("", 13, "bold"),
        command=lambda: _open_instructions_window(function, app or _resolve_app(parent)),
    )
    return btn


def _resolve_app(widget):
    """Walk up the Tk parent chain looking for a get_active_scope method.

    Lets the per-tab buttons find the App instance without the
    caller having to thread it through explicitly.
    """
    cur = widget
    seen = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if hasattr(cur, "get_active_scope"):
            return cur
        cur = getattr(cur, "master", None)
        if cur is None:
            cur = getattr(cur, "_master", None) if False else None
    return None


def _open_instructions_window(function: str, app) -> None:
    """Open the movable non-modal instructions window for ``function``."""
    import customtkinter as ctk

    scope = "(no scope connected)"
    if app is not None:
        active = getattr(app, "get_active_scope", None)
        if active is not None:
            try:
                info = active()
            except Exception:
                info = None
            if info is not None:
                scope = info[2]

    lines = load_instructions(function, scope)

    win = ctk.CTkToplevel(app if app is not None else None)
    title = f"Instructions - {function} - {scope}"
    win.title(title)
    win.geometry("520x420")
    try:
        win.transient(app)
    except Exception:
        pass

    header = ctk.CTkLabel(
        win, text=title, font=("", 14, "bold"), anchor="w",
    )
    header.pack(padx=12, pady=(12, 4), fill="x")

    body = ctk.CTkTextbox(win, wrap="word", activate_scrollbars=True)
    body.pack(padx=12, pady=(0, 12), fill="both", expand=True)
    body.insert("0.0", "\n".join(lines))
    body.configure(state="disabled")

    close = ctk.CTkButton(win, text="Close", command=win.destroy)
    close.pack(padx=12, pady=(0, 12), anchor="e")
