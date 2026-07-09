"""
Arbitrary Waveform Generator tab.

Supports two hardware families. The active dialect is
detected from the ``*IDN?`` response of the connected AWG
(see :mod:`acquisition.arbgen_dialects`):

  * **Siglent SDG2122X**  - default. ``*IDN?`` starts with
    ``Siglent Technologies``.
  * **Agilent / Keysight 33612A** - the user can connect a
    33600A-series AWG and the tab switches to the Agilent
    SCPI dialect automatically.

The dropdown labels and the SCPI tokens per label depend on
the dialect, and so do the per-channel widgets (e.g. phase
is hidden in PULSE mode for both, and the Agilent dropdown
does not offer Triangle because the 33600A does not have
one).

UI layout: two side-by-side panels, one per channel. Each
panel has its own complete set of controls:

  - Wave type dropdown (options vary by dialect).
  - Frequency (Hz) text input.
  - Amplitude (Vpp) text input.
  - Impedance slide switch: HiZ / 50 Ohm (sent immediately).
  - Offset (V) text input.
  - Phase (deg) text input  (hidden in PULSE mode).
  - Pulse width (seconds) text input  (hidden outside PULSE).
  - Update button (sends the six waveform parameters above).
  - Output enable slide switch (immediate, no Apply gate).

The per-channel widget trees are stored under
``self.arbgen_panels[ch]`` (a dict with the wave type, freq,
amp, offset, phase, width, impedance, output switch and
update button). No channel selector: the user works on both
channels at once.

A small "Connected: <model>" indicator at the top of the tab
names the target instrument so the user knows which SCPI
dialect the buttons speak.

The actual SCPI commands are sent through
``acquisition/arbgen_acquisition.py``.
"""
from __future__ import annotations

import customtkinter as ctk

from acquisition.arbgen_acquisition import (
    DEFAULT_DIALECT,
    apply_arbgen_params,
    detect_dialect,
    identify_awg,
    set_arbgen_load,
    set_arbgen_output,
    set_arbgen_pulse_width,
)
from acquisition.arbgen_dialects import (
    ArbgenDialect,
    wave_labels_for,
    wave_token_for,
)


# Sentinel for the initial / unconnected state. We re-detect
# the dialect as soon as the user connects the AWG in the
# Connect tab; until then the panel renders with the
# Siglent defaults so the rest of the tab does not need to
# special-case the unconnected path.
DEFAULT_CONNECTED_LABEL = DEFAULT_DIALECT.label


# Map a "human-friendly" pulse-train label to the SCPI token
# the GUI uses to decide whether to show the phase / width
# inputs. Both dialects share the same user-facing label.
_PULSE_LABEL_SIGLENT = "Pulse train"
_PULSE_LABELS = {"Pulse train", "Pulse"}


def _is_pulse_label(dialect: ArbgenDialect, label: str) -> bool:
    """Return True if ``label`` selects the pulse-train wave type.

    The Siglent dropdown labels it ``Pulse train``; the
    Agilent dropdown labels it ``Pulse train`` too. We accept
    either form to be tolerant of past / future dialects.
    """
    return label in _PULSE_LABELS


def _add_labeled_entry(parent, row: int, label: str, default: str = "",
                       width: int = 140) -> ctk.CTkEntry:
    ctk.CTkLabel(parent, text=label, anchor="w").grid(
        row=row, column=0, padx=(20, 6), pady=4, sticky="w"
    )
    entry = ctk.CTkEntry(parent, width=width, placeholder_text=default)
    entry.grid(row=row, column=1, padx=(0, 20), pady=4, sticky="w")
    return entry


def _add_labeled_option(parent, row: int, label: str, values, default: str = None,
                        width: int = 140) -> ctk.CTkOptionMenu:
    ctk.CTkLabel(parent, text=label, anchor="w").grid(
        row=row, column=0, padx=(20, 6), pady=4, sticky="w"
    )
    if default is None:
        default = values[0]
    menu = ctk.CTkOptionMenu(parent, values=list(values), dynamic_resizing=False, width=width)
    menu.set(default)
    menu.grid(row=row, column=1, padx=(0, 20), pady=4, sticky="w")
    return menu


def _make_slide_switch(parent, row: int, label: str, options,
                       default: str = None) -> ctk.CTkSegmentedButton:
    """Build a slide switch (segmented button) for binary choices.

    ``options`` is an iterable of two strings. The selected
    value can be read with ``.get()`` and a callback is fired
    via ``command`` if provided.
    """
    ctk.CTkLabel(parent, text=label, anchor="w").grid(
        row=row, column=0, padx=(20, 6), pady=4, sticky="w"
    )
    options = list(options)
    if default is None:
        default = options[0]
    sw = ctk.CTkSegmentedButton(
        parent, values=options, width=180,
    )
    sw.set(default)
    sw.grid(row=row, column=1, padx=(0, 20), pady=4, sticky="w")
    return sw


def _build_channel_panel(parent: ctk.CTkFrame, channel: str,
                         dialect: ArbgenDialect) -> dict:
    """Build one per-channel control panel.

    Returns a dict of widgets keyed by attribute name so the
    action handlers can read each control's value. The
    ``phase`` and ``width`` entries carry their labels in the
    same dict (``phase_label``, ``width_label``) so the
    per-wave handler can hide / show them without rebuilding
    the panel.
    """
    panel = ctk.CTkFrame(parent)
    panel.grid_columnconfigure((0, 1), weight=1)

    # --- Channel header -----------------------------------------------------
    header = ctk.CTkLabel(
        panel, text=f"Channel {channel[-1]}",
        font=("", 15, "bold"), anchor="center",
    )
    header.grid(row=0, column=0, columnspan=2, padx=20, pady=(12, 8), sticky="ew")

    # --- Wave type ---------------------------------------------------------
    ctk.CTkLabel(panel, text="Waveform", font=("", 12, "bold"),
                 anchor="w").grid(row=1, column=0, columnspan=2, padx=20,
                                  pady=(8, 4), sticky="w")
    wave_labels = wave_labels_for(dialect)
    waveform = _add_labeled_option(
        panel, row=2, label="Type:",
        values=wave_labels,
        default=wave_labels[0], width=160,
    )
    # Refresh phase / width visibility whenever the user changes
    # the wave type so PULSE hides the phase field and other
    # modes hide the pulse width.
    waveform.configure(
        command=lambda _value, ch=channel: _refresh_pulse_visibility(self, ch)
    )

    # --- Frequency / Amplitude / Offset / Phase / Width text inputs -------
    ctk.CTkLabel(panel, text="Parameters", font=("", 12, "bold"),
                 anchor="w").grid(row=3, column=0, columnspan=2, padx=20,
                                  pady=(12, 4), sticky="w")
    freq = _add_labeled_entry(panel, row=4, label="Frequency (Hz):", default="1000")
    amp = _add_labeled_entry(panel, row=5, label="Amplitude (Vpp):", default="1.0")
    offset = _add_labeled_entry(panel, row=6, label="Offset (V):", default="0.0")
    phase_label = ctk.CTkLabel(panel, text="Phase (deg):", anchor="w")
    phase_label.grid(row=7, column=0, padx=(20, 6), pady=4, sticky="w")
    phase = ctk.CTkEntry(panel, width=140, placeholder_text="0")
    phase.grid(row=7, column=1, padx=(0, 20), pady=4, sticky="w")
    width_label = ctk.CTkLabel(panel, text="Pulse width (s):", anchor="w")
    width_label.grid(row=8, column=0, padx=(20, 6), pady=4, sticky="w")
    width = ctk.CTkEntry(panel, width=140, placeholder_text="10E-6")
    width.grid(row=8, column=1, padx=(0, 20), pady=4, sticky="w")

    # --- Impedance slide switch (immediate) -------------------------------
    impedance = _make_slide_switch(
        panel, row=9, label="Impedance:",
        options=["HiZ", "50 Ohm"], default="HiZ",
    )

    # --- Update + On/Off on the same row ---------------------------------
    # Column 0 holds the "Apply" sub-group (label + Update button),
    # column 1 holds the "Output" sub-group (label + slide switch).
    # Both sub-groups share a single row so the two controls are
    # at the same height.
    ctk.CTkLabel(panel, text="Apply", font=("", 12, "bold"),
                 anchor="w").grid(row=10, column=0, padx=(20, 6),
                                  pady=(12, 4), sticky="w")
    update_button = ctk.CTkButton(panel, text="Update", width=160)
    update_button.grid(row=11, column=0, padx=(20, 6), pady=(4, 12), sticky="w")

    ctk.CTkLabel(panel, text="Output", font=("", 12, "bold"),
                 anchor="w").grid(row=10, column=1, padx=(6, 20),
                                  pady=(12, 4), sticky="w")
    # Slide switch without the helper's "On/Off:" label — the
    # "Output" header above already names the section.
    output = ctk.CTkSegmentedButton(
        panel, values=["OFF", "ON"], width=180,
    )
    output.set("OFF")
    output.grid(row=11, column=1, padx=(6, 20), pady=(4, 12), sticky="w")

    # Initial state of the phase / width visibility: depends on
    # whether the default wave type is pulse.
    if _is_pulse_label(dialect, wave_labels[0]):
        # Default is pulse (e.g. an Agilent unit the user
        # never touched). Hide phase, show width.
        phase_label.grid_remove()
        phase.grid_remove()
    else:
        # Default is non-pulse. Hide width, show phase.
        width_label.grid_remove()
        width.grid_remove()

    return {
        "frame": panel,
        "channel": channel,
        "waveform": waveform,
        "freq": freq,
        "amp": amp,
        "offset": offset,
        "phase": phase,
        "phase_label": phase_label,
        "width": width,
        "width_label": width_label,
        "impedance": impedance,
        "output": output,
        "update_button": update_button,
    }


def _refresh_pulse_visibility(self, channel: str) -> None:
    """Show / hide the phase and width inputs based on the active wave.

    * Pulse-train mode  -> hide ``phase``, show ``width``.
    * Any other mode    -> show ``phase``, hide ``width``.

    The user can flip back and forth freely; we just call
    ``grid_remove`` on the rows that should disappear and
    ``grid`` to bring them back. Tk does not animate this so
    the change is instant.
    """
    panel = self.arbgen_panels.get(channel)
    if panel is None:
        return
    label = panel["waveform"].get()
    dialect = self.arbgen_dialect
    is_pulse = _is_pulse_label(dialect, label)
    if is_pulse:
        panel["phase_label"].grid_remove()
        panel["phase"].grid_remove()
        panel["width_label"].grid()
        panel["width"].grid()
    else:
        panel["width_label"].grid_remove()
        panel["width"].grid_remove()
        panel["phase_label"].grid()
        panel["phase"].grid()


def setting_arbgen(self) -> None:
    """Build the ArbGen tab with two side-by-side channel panels.

    The dialect is set to the default (Siglent) at construction
    time. Once the user connects an AWG in the Connect tab,
    the dialog is re-detected (see
    :func:`arbgen_update_connected`) and the panel is rebuilt
    so the wave-type dropdown matches the connected scope.
    """
    # WIP suffix in the tab title for clarity.
    if "ArbGen" not in self.tabview._tab_dict:
        self.tabview.add("ArbGen")
    tab = self.tabview.tab("ArbGen")
    # Two equal-weight columns: one per channel.
    tab.grid_columnconfigure(0, weight=1)
    tab.grid_columnconfigure(1, weight=1)
    tab.grid_rowconfigure(0, weight=0)  # connected indicator
    tab.grid_rowconfigure(1, weight=1)  # channel panels

    # Connected instrument indicator (top, spans both columns).
    self.arbgen_connected_label = ctk.CTkLabel(
        tab, text=f"Connected: {DEFAULT_CONNECTED_LABEL}",
        font=("", 12, "bold"), text_color="#2ea043", anchor="w",
    )
    self.arbgen_connected_label.grid(
        row=0, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w",
    )

    self.arbgen_dialect: ArbgenDialect = DEFAULT_DIALECT

    # Two scrollable channel panels, side by side, below the indicator.
    self.arbgen_panels: dict[str, dict] = {}
    _populate_panels(self, tab, self.arbgen_dialect)


def _populate_panels(self, tab, dialect: ArbgenDialect) -> None:
    """(Re)build the per-channel panels for ``dialect``.

    Called once on tab construction and again whenever the
    user connects an AWG whose detected dialect differs from
    the current one. We destroy the existing panel frames
    first so the rebuild is clean.
    """
    # Drop any previously built panels so the new ones can use
    # the same grid cells.
    for ch, panel in list(self.arbgen_panels.items()):
        try:
            panel["frame"].destroy()
        except Exception:
            pass
    self.arbgen_panels = {}

    for col, channel in enumerate(("CH1", "CH2")):
        panel_frame = ctk.CTkScrollableFrame(tab)
        panel_frame.grid(row=1, column=col, padx=8, pady=8, sticky="nsew")
        widgets = _build_channel_panel(panel_frame, channel, dialect)
        widgets["frame"].pack(fill="both", expand=True, padx=4, pady=4)
        # Wire the per-channel buttons to the per-channel handlers.
        widgets["update_button"].configure(
            command=lambda ch=channel: arbgen_update(self, ch)
        )
        widgets["output"].configure(
            command=lambda value, ch=channel: arbgen_toggle_output(self, ch, value)
        )
        # Impedance and pulse width are sent immediately too,
        # so a click on the slide switch hits the scope right
        # away. Pulse width uses a focus-out binding rather
        # than a typing keystroke so we do not spam the scope
        # on every character.
        widgets["impedance"].configure(
            command=lambda value, ch=channel: arbgen_change_load(self, ch, value)
        )
        widgets["width"].bind(
            "<FocusOut>",
            lambda _event, ch=channel: arbgen_change_width(self, ch),
        )
        self.arbgen_panels[channel] = widgets


def arbgen_update_connected(self) -> None:
    """Re-detect the AWG model and rebuild the panel if the dialect changed.

    Called from the Connect tab success handler so that
    connecting a different AWG switches the SCPI dialect on
    the fly. The connected indicator is updated with the
    raw ``*IDN?`` response so the user can see exactly which
    model the program recognised.

    Always updates ``self.arbgen_dialect`` so a freshly
    connected AWG is reflected immediately, even if the
    user never disconnected the previous one (e.g. switched
    the IP in the Connect card and pressed Connect again).
    """
    conn = _arbgen_live_conn(self)
    idn = identify_awg(conn)
    if idn:
        self.arbgen_connected_label.configure(
            text=f"Connected: {idn}", text_color="#2ea043",
        )
    else:
        self.arbgen_connected_label.configure(
            text="Connected: (none)", text_color="#a0a0a0",
        )
    new_dialect = detect_dialect(conn) if conn is not None else DEFAULT_DIALECT
    if new_dialect.key != self.arbgen_dialect.key:
        self.arbgen_dialect = new_dialect
        _populate_panels(self, self.tabview.tab("ArbGen"), self.arbgen_dialect)
    else:
        # Same dialect, but make sure the cached attribute is
        # in sync with the freshly-detected object (defensive
        # against any code path that swapped the dialect
        # without rebuilding the panels).
        self.arbgen_dialect = new_dialect


# ---- Action handlers (called by the buttons / slide switches) -------------
#
# These read the per-channel control values from
# ``self.arbgen_panels[channel]`` and delegate the actual SCPI
# work to ``acquisition.arbgen_acquisition``.


def _read_panel_params(self, channel: str) -> dict:
    """Build the params dict for a channel from the live widgets."""
    panel = self.arbgen_panels[channel]
    label = panel["waveform"].get()
    return {
        "channel": channel,
        "waveform_label": label,
        "waveform_scpi": wave_token_for(self.arbgen_dialect, label),
        "frequency_hz": panel["freq"].get(),
        "amplitude_vpp": panel["amp"].get(),
        "impedance": panel["impedance"].get(),
        "offset_v": panel["offset"].get(),
        "phase_deg": panel["phase"].get(),
        "width_s": panel["width"].get(),
    }


def arbgen_update(self, channel: str) -> None:
    """Send the Update-gated parameters of ``channel`` to the AWG.

    Does not touch the on/off or impedance state (those have
    their own immediate switches).
    """
    params = _read_panel_params(self, channel)
    print(f"[ArbGen] Update CH={params['channel']} "
          f"wave={params['waveform_scpi']} "
          f"freq={params['frequency_hz']}Hz "
          f"amp={params['amplitude_vpp']}Vpp "
          f"Z={params['impedance']} "
          f"offset={params['offset_v']}V "
          f"phase={params['phase_deg']}deg "
          f"width={params['width_s']}s")
    try:
        apply_arbgen_params(params, config=self.config.config,
                            conn=_arbgen_live_conn(self),
                            dialect=self.arbgen_dialect)
    except Exception as e:
        print(f"[ArbGen] apply_arbgen_params failed: {e}")


def _arbgen_live_conn(app):
    """Return the live pyvisa connection to the AWG, or None.

    The Connect tab keeps an open ``InstrumentConnection`` in
    ``app.connect_cards["arbGen"]["connection"]`` once the
    user has clicked Connect. We reuse that handle so the
    per-channel switches talk to the same session the command
    line uses. Returns ``None`` if the AWG is not connected,
    in which case the adapter just prints the SCPI line.

    Falls back to ``app.gui_funcs`` (the legacy facade) for
    backwards compatibility with older test stubs.
    """
    cards = getattr(app, "connect_cards", None)
    if not cards:
        return None
    # Try the standard "arbGen" key first.
    for key in ("arbGen",):
        widgets = cards.get(key)
        if isinstance(widgets, dict):
            conn = widgets.get("connection")
            if conn is not None:
                return conn
    return None


def arbgen_toggle_output(self, channel: str, value: str = None) -> None:
    """Immediate on/off. Fires whenever the channel's slide switch moves."""
    panel = self.arbgen_panels[channel]
    state = value if value is not None else panel["output"].get()
    print(f"[ArbGen] Output {state} on {channel}")
    try:
        set_arbgen_output(channel=channel, on=(state == "ON"),
                          config=self.config.config,
                          conn=_arbgen_live_conn(self),
                          dialect=self.arbgen_dialect)
    except Exception as e:
        print(f"[ArbGen] set_arbgen_output failed: {e}")


def arbgen_change_load(self, channel: str, value: str) -> None:
    """Immediate impedance change. Fires when the slide switch moves."""
    print(f"[ArbGen] Load {value} on {channel}")
    try:
        set_arbgen_load(channel=channel, impedance=value,
                        config=self.config.config,
                        conn=_arbgen_live_conn(self),
                        dialect=self.arbgen_dialect)
    except Exception as e:
        print(f"[ArbGen] set_arbgen_load failed: {e}")


def arbgen_change_width(self, channel: str) -> None:
    """Pulse width change, fired on focus-out (so we do not
    spam the scope on every keystroke)."""
    panel = self.arbgen_panels[channel]
    raw = panel["width"].get().strip() or "10E-6"
    try:
        width = float(raw)
    except ValueError:
        print(f"[ArbGen] Bad pulse width {raw!r}, ignoring.")
        return
    print(f"[ArbGen] Pulse width {width:.3E}s on {channel}")
    try:
        set_arbgen_pulse_width(channel=channel, width_s=width,
                                config=self.config.config,
                                conn=_arbgen_live_conn(self),
                                dialect=self.arbgen_dialect)
    except Exception as e:
        print(f"[ArbGen] set_arbgen_pulse_width failed: {e}")


if __name__ == "__main__":
    # Headless sanity check: build a Tk root and run the
    # constructor to ensure the widgets are well-formed.
    import os
    if "DISPLAY" in os.environ or os.name == "nt":
        try:
            root = ctk.CTk()
            class _Stub:
                pass
            stub = _Stub()
            stub.tabview = type("T", (), {"_tab_dict": {}})()
            setting_arbgen(stub)
            root.destroy()
            print("setting_arbgen OK")
        except Exception as e:
            print(f"setting_arbgen failed: {e}")
    else:
        print("no display; skipping")
