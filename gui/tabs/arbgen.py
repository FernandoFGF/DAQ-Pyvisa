"""
Arbitrary Waveform Generator tab.

Hardware target: Siglent SDG2122X
(*IDN: Siglent Technologies,SDG2122X,SDG2XCAC6R0231,2.01.01.35R3B2).

UI controls:
  - Wave type dropdown: Sine, Square, Triangle, Pulse train.
  - Frequency (Hz) text input.
  - Amplitude (Vpp) text input.
  - Impedance slide switch: HiZ / 50 Ohm.
  - Offset (V) text input.
  - Phase (deg) text input.
  - Channel slide switch: CH1 / CH2.
  - Output enable slide switch (immediate, no Apply gate).
  - Update button: sends the other six parameters (wave type,
    frequency, amplitude, impedance, offset, phase) to the
    selected channel in a single burst.

The actual SCPI commands are sent through a small adapter in
``acquisition/arbgen_acquisition.py`` so the GUI does not depend
on pyvisa directly. The adapter is a thin wrapper around
``acquisition.connection.open_pyvisa`` and falls back to a
``FakeArbGen`` so the unit tests can run without hardware.
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


def setting_arbgen(self) -> None:
    """Build the ArbGen tab. All controls are wired to ``self``
    attributes; the Apply / on-off buttons print their values
    and call into ``acquisition.arbgen_acquisition`` (filled in
    in a follow-up)."""
    # WIP suffix in the tab title for clarity.
    if "ArbGen (WIP)" not in self.tabview._tab_dict:
        self.tabview.add("ArbGen (WIP)")
    tab = self.tabview.tab("ArbGen (WIP)")
    tab.grid_columnconfigure(0, weight=0)
    tab.grid_columnconfigure(1, weight=3)
    tab.grid_rowconfigure(0, weight=1)

    # Left column: control panel inside a scrollable frame.
    controls = ctk.CTkScrollableFrame(tab, width=320)
    controls.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    controls.grid_columnconfigure((0, 1), weight=1)

    banner = _wip_banner(controls)
    banner.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 12), sticky="ew")

    # --- Channel slide switch (CH1 / CH2) ----------------------------------
    ctk.CTkLabel(controls, text="Channel", font=("", 13, "bold"),
                 anchor="w").grid(row=1, column=0, columnspan=2, padx=20,
                                  pady=(8, 4), sticky="w")
    self.arbgen_channel = _make_slide_switch(
        controls, row=2, label="Channel:",
        options=["CH1", "CH2"], default="CH1",
    )

    # --- Wave type dropdown ------------------------------------------------
    ctk.CTkLabel(controls, text="Waveform", font=("", 13, "bold"),
                 anchor="w").grid(row=3, column=0, columnspan=2, padx=20,
                                  pady=(16, 4), sticky="w")
    self.arbgen_waveform = _add_labeled_option(
        controls, row=4, label="Type:",
        values=WAVEFORM_LABELS, default="Sine", width=160,
    )

    # --- Frequency / Amplitude / Offset / Phase text inputs ---------------
    ctk.CTkLabel(controls, text="Parameters", font=("", 13, "bold"),
                 anchor="w").grid(row=5, column=0, columnspan=2, padx=20,
                                  pady=(16, 4), sticky="w")
    self.arbgen_freq = _add_labeled_entry(
        controls, row=6, label="Frequency (Hz):", default="1000",
    )
    self.arbgen_amp = _add_labeled_entry(
        controls, row=7, label="Amplitude (Vpp):", default="1.0",
    )
    self.arbgen_offset = _add_labeled_entry(
        controls, row=8, label="Offset (V):", default="0.0",
    )
    self.arbgen_phase = _add_labeled_entry(
        controls, row=9, label="Phase (deg):", default="0",
    )

    # --- Impedance slide switch (HiZ / 50 Ohm) ----------------------------
    self.arbgen_impedance = _make_slide_switch(
        controls, row=10, label="Impedance:",
        options=["HiZ", "50 Ohm"], default="HiZ",
    )

    # --- Update button (sends the parameters above) -----------------------
    ctk.CTkLabel(controls, text="Apply", font=("", 13, "bold"),
                 anchor="w").grid(row=11, column=0, columnspan=2, padx=20,
                                  pady=(16, 4), sticky="w")
    self.arbgen_update_button = ctk.CTkButton(
        controls, text="Update",
        command=lambda: arbgen_update(self), width=180,
    )
    self.arbgen_update_button.grid(
        row=12, column=0, columnspan=2, padx=20, pady=(4, 12), sticky="w",
    )

    # --- Output enable slide switch (immediate, no Apply gate) -----------
    ctk.CTkLabel(controls, text="Output", font=("", 13, "bold"),
                 anchor="w").grid(row=13, column=0, columnspan=2, padx=20,
                                  pady=(8, 4), sticky="w")
    self.arbgen_output = _make_slide_switch(
        controls, row=14, label="On/Off:",
        options=["OFF", "ON"], default="OFF",
    )
    # The on/off switch fires immediately (no Apply gate).
    self.arbgen_output.configure(command=lambda value: arbgen_toggle_output(self, value))

    # --- Right column: empty plot placeholder ------------------------------
    plot = ctk.CTkFrame(tab)
    plot.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    plot.grid_rowconfigure(0, weight=1)
    plot.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        plot,
        text="(Plot placeholder — waveform preview will be added with the logic.)",
        text_color="#888",
    ).grid(row=0, column=0, padx=20, pady=20)


# ---- Action handlers (called by the buttons / slide switches) -------------
#
# These are intentionally light: they read the current control
# values, print a structured one-liner to the terminal, and
# delegate the actual SCPI work to ``acquisition.arbgen_acquisition``
# which will be filled in next. Tests can monkey-patch the
# acquisition function or assert on the print output.


def arbgen_update(self) -> None:
    """Send the six parameters above to the selected channel.

    Triggered by the Update button. Does not touch the on/off
    state (that has its own slide switch).
    """
    params = {
        "channel": self.arbgen_channel.get(),
        "waveform_label": self.arbgen_waveform.get(),
        "waveform_scpi": WAVEFORM_BY_LABEL.get(self.arbgen_waveform.get(), "SINE"),
        "frequency_hz": self.arbgen_freq.get(),
        "amplitude_vpp": self.arbgen_amp.get(),
        "impedance": self.arbgen_impedance.get(),
        "offset_v": self.arbgen_offset.get(),
        "phase_deg": self.arbgen_phase.get(),
    }
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


def arbgen_toggle_output(self, value: str = None) -> None:
    """Immediate on/off. Fires whenever the slide switch moves.

    ``value`` is the segmented-button selection ("ON" or "OFF").
    Falls back to ``self.arbgen_output.get()`` when not given
    (e.g. for direct test calls).
    """
    state = value if value is not None else self.arbgen_output.get()
    channel = self.arbgen_channel.get()
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
