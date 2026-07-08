"""
Arbitrary Waveform Generator tab.

Hardware target: Siglent SDG2122X
(*IDN: Siglent Technologies,SDG2122X,SDG2XCAC6R0231,2.01.01.35R3B2).

UI layout: two side-by-side panels, one per channel. Each panel
has its own complete set of controls:

  - Wave type dropdown: Sine, Square, Triangle, Pulse train.
  - Frequency (Hz) text input.
  - Amplitude (Vpp) text input.
  - Impedance slide switch: HiZ / 50 Ohm.
  - Offset (V) text input.
  - Phase (deg) text input.
  - Update button (sends the six parameters above).
  - Output enable slide switch (immediate, no Apply gate).

The per-channel widget trees are stored under
``self.arbgen_panels[ch]`` (a dict with the wave type, freq,
amp, offset, phase, impedance, output switch and update
button). No channel selector: the user works on both
channels at once.

The actual SCPI commands are sent through a small adapter in
``acquisition/arbgen_acquisition.py`` so the GUI does not depend
on pyvisa directly.
"""
from __future__ import annotations

import customtkinter as ctk

from acquisition.arbgen_acquisition import (
    apply_arbgen_params,
    set_arbgen_output,
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


def _wip_banner(parent: ctk.CTkFrame) -> ctk.CTkLabel:
    """Yellow WIP banner. The UI is wired but the SCPI backend
    is still being filled in. SCPI commands land in
    ``acquisition/arbgen_acquisition.py``."""
    return ctk.CTkLabel(
        parent,
        text="⚠ WIP — UI ready, SCPI backend pending. "
             "Siglent SDG2122X is the first target.",
        font=("", 12, "bold"),
        text_color="#7a5b00",
        fg_color="#fff3bf",
        corner_radius=6,
        padx=12,
        pady=8,
        anchor="w",
    )


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
        font=("", 15, "bold"), anchor="w",
    )
    header.grid(row=0, column=0, columnspan=2, padx=20, pady=(12, 8), sticky="w")

    # --- Wave type ---------------------------------------------------------
    ctk.CTkLabel(panel, text="Waveform", font=("", 12, "bold"),
                 anchor="w").grid(row=1, column=0, columnspan=2, padx=20,
                                  pady=(8, 4), sticky="w")
    waveform = _add_labeled_option(
        panel, row=2, label="Type:",
        values=WAVEFORM_LABELS, default="Sine", width=160,
    )

    # --- Frequency / Amplitude / Offset / Phase text inputs ---------------
    ctk.CTkLabel(panel, text="Parameters", font=("", 12, "bold"),
                 anchor="w").grid(row=3, column=0, columnspan=2, padx=20,
                                  pady=(12, 4), sticky="w")
    freq = _add_labeled_entry(panel, row=4, label="Frequency (Hz):", default="1000")
    amp = _add_labeled_entry(panel, row=5, label="Amplitude (Vpp):", default="1.0")
    offset = _add_labeled_entry(panel, row=6, label="Offset (V):", default="0.0")
    phase = _add_labeled_entry(panel, row=7, label="Phase (deg):", default="0")

    # --- Impedance slide switch -------------------------------------------
    impedance = _make_slide_switch(
        panel, row=8, label="Impedance:",
        options=["HiZ", "50 Ohm"], default="HiZ",
    )

    # --- Update button ----------------------------------------------------
    ctk.CTkLabel(panel, text="Apply", font=("", 12, "bold"),
                 anchor="w").grid(row=9, column=0, columnspan=2, padx=20,
                                  pady=(12, 4), sticky="w")
    update_button = ctk.CTkButton(panel, text="Update", width=160)
    update_button.grid(row=10, column=0, columnspan=2, padx=20, pady=(4, 8), sticky="w")

    # --- Output enable slide switch (immediate) --------------------------
    ctk.CTkLabel(panel, text="Output", font=("", 12, "bold"),
                 anchor="w").grid(row=11, column=0, columnspan=2, padx=20,
                                  pady=(8, 4), sticky="w")
    output = _make_slide_switch(
        panel, row=12, label="On/Off:",
        options=["OFF", "ON"], default="OFF",
    )

    return {
        "frame": panel,
        "channel": channel,
        "waveform": waveform,
        "freq": freq,
        "amp": amp,
        "offset": offset,
        "phase": phase,
        "impedance": impedance,
        "output": output,
        "update_button": update_button,
    }


def setting_arbgen(self) -> None:
    """Build the ArbGen tab with two side-by-side channel panels."""
    # WIP suffix in the tab title for clarity.
    if "ArbGen (WIP)" not in self.tabview._tab_dict:
        self.tabview.add("ArbGen (WIP)")
    tab = self.tabview.tab("ArbGen (WIP)")
    # Two equal-weight columns: one per channel.
    tab.grid_columnconfigure(0, weight=1)
    tab.grid_columnconfigure(1, weight=1)
    tab.grid_rowconfigure(0, weight=1)

    # WIP banner spans both columns at the top.
    banner = _wip_banner(tab)
    banner.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 6), sticky="ew")

    # Two scrollable channel panels, side by side, below the banner.
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
        self.arbgen_panels[channel] = widgets


# ---- Action handlers (called by the buttons / slide switches) -------------
#
# These read the per-channel control values from
# ``self.arbgen_panels[channel]`` and delegate the actual SCPI
# work to ``acquisition.arbgen_acquisition``, which is still a
# stub. Tests can monkey-patch the acquisition function or
# assert on the print output.


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
    }


def arbgen_update(self, channel: str) -> None:
    """Send the six parameters of ``channel`` to the AWG.

    Triggered by the channel's Update button. Does not touch
    the on/off state (that has its own slide switch).
    """
    params = _read_panel_params(self, channel)
    print(f"[ArbGen] Update CH={params['channel']} "
          f"wave={params['waveform_scpi']} "
          f"freq={params['frequency_hz']}Hz "
          f"amp={params['amplitude_vpp']}Vpp "
          f"Z={params['impedance']} "
          f"offset={params['offset_v']}V "
          f"phase={params['phase_deg']}deg")
    try:
        apply_arbgen_params(params, config=self.config.config)
    except Exception as e:
        print(f"[ArbGen] apply_arbgen_params failed: {e}")


def arbgen_toggle_output(self, channel: str, value: str = None) -> None:
    """Immediate on/off. Fires whenever the channel's slide switch moves.

    ``value`` is the segmented-button selection ("ON" or "OFF").
    Falls back to ``self.arbgen_panels[channel]['output'].get()``
    when not given (e.g. for direct test calls).
    """
    panel = self.arbgen_panels[channel]
    state = value if value is not None else panel["output"].get()
    print(f"[ArbGen] Output {state} on {channel}")
    try:
        set_arbgen_output(channel=channel, on=(state == "ON"),
                          config=self.config.config)
    except Exception as e:
        print(f"[ArbGen] set_arbgen_output failed: {e}")


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
