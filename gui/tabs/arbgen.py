"""
Arbitrary Waveform Generator tab.

Hardware target: Siglent SDG2122X
(*IDN: Siglent Technologies,SDG2122X,SDG2XCAC6R0231,2.01.01.35R3B2).

UI layout: two side-by-side panels, one per channel. Each panel
has its own complete set of controls:

  - Wave type dropdown: Sine, Square, Triangle, Pulse train.
  - Frequency (Hz) text input.
  - Amplitude (Vpp) text input.
  - Impedance slide switch: HiZ / 50 Ohm (sent immediately).
  - Offset (V) text input.
  - Phase (deg) text input.
  - Pulse width (seconds) text input.
  - Update button (sends the six waveform parameters above).
  - Output enable slide switch (immediate, no Apply gate).

The per-channel widget trees are stored under
``self.arbgen_panels[ch]`` (a dict with the wave type, freq,
amp, offset, phase, width, impedance, output switch and
update button). No channel selector: the user works on both
channels at once.

A small "Connected: Siglent SDG2122X" indicator at the top
of the tab names the target instrument so the user knows
which SCPI dialect the buttons speak.

The actual SCPI commands are sent through
``acquisition/arbgen_acquisition.py``.
"""
from __future__ import annotations

import customtkinter as ctk

from acquisition.arbgen_acquisition import (
    apply_arbgen_params,
    set_arbgen_load,
    set_arbgen_output,
    set_arbgen_pulse_width,
)


# Wave-type dropdown options. Keys are the SCPI WVTP tokens for
# the Siglent SDG2122X; values are the user-facing labels.
WAVEFORM_OPTIONS = [
    ("Sine", "SINE"),
    ("Square", "SQUARE"),
    ("Triangle", "RAMP"),   # Siglent uses RAMP for triangle.
    ("Pulse train", "PULSE"),
]
WAVEFORM_LABELS = [label for label, _ in WAVEFORM_OPTIONS]
WAVEFORM_BY_LABEL = dict(WAVEFORM_OPTIONS)


# Display name shown in the "Connected:" indicator. Updated
# automatically from the Connect tab when the user connects
# the AWG; falls back to this string otherwise.
DEFAULT_CONNECTED_LABEL = "Siglent SDG2122X"


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


def _build_channel_panel(parent: ctk.CTkFrame, channel: str) -> dict:
    """Build one per-channel control panel.

    Returns a dict of widgets keyed by attribute name so the
    action handlers can read each control's value.
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
    waveform = _add_labeled_option(
        panel, row=2, label="Type:",
        values=WAVEFORM_LABELS, default="Sine", width=160,
    )

    # --- Frequency / Amplitude / Offset / Phase / Width text inputs -------
    ctk.CTkLabel(panel, text="Parameters", font=("", 12, "bold"),
                 anchor="w").grid(row=3, column=0, columnspan=2, padx=20,
                                  pady=(12, 4), sticky="w")
    freq = _add_labeled_entry(panel, row=4, label="Frequency (Hz):", default="1000")
    amp = _add_labeled_entry(panel, row=5, label="Amplitude (Vpp):", default="1.0")
    offset = _add_labeled_entry(panel, row=6, label="Offset (V):", default="0.0")
    phase = _add_labeled_entry(panel, row=7, label="Phase (deg):", default="0")
    width = _add_labeled_entry(panel, row=8, label="Pulse width (s):",
                               default="10E-6")

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

    return {
        "frame": panel,
        "channel": channel,
        "waveform": waveform,
        "freq": freq,
        "amp": amp,
        "offset": offset,
        "phase": phase,
        "width": width,
        "impedance": impedance,
        "output": output,
        "update_button": update_button,
    }


def setting_arbgen(self) -> None:
    """Build the ArbGen tab with two side-by-side channel panels."""
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

    # Two scrollable channel panels, side by side, below the indicator.
    self.arbgen_panels: dict[str, dict] = {}
    for col, channel in enumerate(("CH1", "CH2")):
        panel_frame = ctk.CTkScrollableFrame(tab)
        panel_frame.grid(row=1, column=col, padx=8, pady=8, sticky="nsew")
        widgets = _build_channel_panel(panel_frame, channel)
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


# ---- Action handlers (called by the buttons / slide switches) -------------
#
# These read the per-channel control values from
# ``self.arbgen_panels[channel]`` and delegate the actual SCPI
# work to ``acquisition.arbgen_acquisition``.


def _read_panel_params(self, channel: str) -> dict:
    """Build the params dict for a channel from the live widgets."""
    panel = self.arbgen_panels[channel]
    return {
        "channel": channel,
        "waveform_label": panel["waveform"].get(),
        "waveform_scpi": WAVEFORM_BY_LABEL.get(panel["waveform"].get(), "SINE"),
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
        apply_arbgen_params(params, config=self.config.config)
    except Exception as e:
        print(f"[ArbGen] apply_arbgen_params failed: {e}")


def arbgen_toggle_output(self, channel: str, value: str = None) -> None:
    """Immediate on/off. Fires whenever the channel's slide switch moves."""
    panel = self.arbgen_panels[channel]
    state = value if value is not None else panel["output"].get()
    print(f"[ArbGen] Output {state} on {channel}")
    try:
        set_arbgen_output(channel=channel, on=(state == "ON"),
                          config=self.config.config)
    except Exception as e:
        print(f"[ArbGen] set_arbgen_output failed: {e}")


def arbgen_change_load(self, channel: str, value: str) -> None:
    """Immediate impedance change. Fires when the slide switch moves."""
    print(f"[ArbGen] Load {value} on {channel}")
    try:
        set_arbgen_load(channel=channel, impedance=value,
                         config=self.config.config)
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
                                config=self.config.config)
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
