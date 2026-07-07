"""
Arbitrary Waveform Generator tab (WIP).

UI scaffold for the ArbGen panel. No acquisition or SCPI logic
yet — controls are present and grouped the way a typical AWG
control surface looks, but the Run / Stop buttons are disabled
and clearly labelled WIP. The next iteration will wire the
controls to a new acquisition/arbgen module.

WIP marker: a 'WIP' badge in the tab title, and a banner at the
top of the panel explaining the current state. Search for "WIP"
to find every spot still pending.
"""
from __future__ import annotations

import customtkinter as ctk


WAVEFORM_OPTIONS = [
    "Sine",
    "Square",
    "Ramp",
    "Pulse",
    "Noise",
    "DC",
    "Arbitrary",
]

MODULATION_OPTIONS = [
    "Off",
    "AM",
    "FM",
    "PM",
    "FSK",
    "ASK",
    "PSK",
]

TRIGGER_SOURCES = [
    "Immediate",
    "External",
    "Manual",
    "Timer",
]


def _wip_banner(parent: ctk.CTkFrame) -> ctk.CTkLabel:
    """Yellow WIP banner so the user knows nothing happens yet."""
    return ctk.CTkLabel(
        parent,
        text="⚠ WIP — UI scaffold only. Run/Stop buttons are disabled. "
             "Logic will be wired in a follow-up.",
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
    menu = ctk.CTkOptionMenu(parent, values=values, dynamic_resizing=False, width=width)
    menu.set(default)
    menu.grid(row=row, column=1, padx=(0, 20), pady=4, sticky="w")
    return menu


def _add_dual_entry(parent, row: int, label_a: str, label_b: str,
                    default_a: str = "", default_b: str = ""):
    """Two entries side by side, sharing row."""
    ctk.CTkLabel(parent, text=label_a, anchor="w").grid(
        row=row, column=0, padx=(20, 6), pady=4, sticky="w"
    )
    a = ctk.CTkEntry(parent, width=120, placeholder_text=default_a)
    a.grid(row=row, column=1, padx=(0, 12), pady=4, sticky="w")
    ctk.CTkLabel(parent, text=label_b, anchor="w").grid(
        row=row, column=2, padx=(6, 6), pady=4, sticky="w"
    )
    b = ctk.CTkEntry(parent, width=120, placeholder_text=default_b)
    b.grid(row=row, column=3, padx=(0, 20), pady=4, sticky="w")
    return a, b


def _add_wip_button(parent, text: str) -> ctk.CTkButton:
    btn = ctk.CTkButton(parent, text=text, state="disabled", width=160)
    return btn


def setting_arbgen(self) -> None:
    """Build the ArbGen tab. All controls are placeholders (WIP)."""
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
    controls.grid_columnconfigure((0, 1, 2, 3), weight=1)

    banner = _wip_banner(controls)
    banner.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 12), sticky="ew")

    # --- Channel & Function -------------------------------------------------
    ctk.CTkLabel(controls, text="Channel", font=("", 13, "bold"),
                 anchor="w").grid(row=1, column=0, columnspan=4, padx=20,
                                  pady=(8, 4), sticky="w")
    _add_labeled_option(controls, row=2, label="Output",
                        values=["CH1", "CH2"], default="CH1", width=120)
    _add_labeled_option(controls, row=3, label="Function",
                        values=WAVEFORM_OPTIONS, default="Sine", width=120)

    # --- Frequency / Period / Phase ----------------------------------------
    ctk.CTkLabel(controls, text="Frequency", font=("", 13, "bold"),
                 anchor="w").grid(row=4, column=0, columnspan=4, padx=20,
                                  pady=(16, 4), sticky="w")
    _add_dual_entry(controls, row=5, label_a="Freq (Hz):", label_b="Period (s):",
                    default_a="1000", default_b="0.001")
    _add_dual_entry(controls, row=6, label_a="Phase (deg):",
                    label_b="",
                    default_a="0")

    # --- Amplitude / Offset -----------------------------------------------
    ctk.CTkLabel(controls, text="Amplitude", font=("", 13, "bold"),
                 anchor="w").grid(row=7, column=0, columnspan=4, padx=20,
                                  pady=(16, 4), sticky="w")
    _add_dual_entry(controls, row=8, label_a="Amplitude (Vpp):",
                    label_b="Offset (V):", default_a="1.0", default_b="0.0")
    _add_dual_entry(controls, row=9, label_a="High (V):", label_b="Low (V):",
                    default_a="0.5", default_b="-0.5")
    _add_labeled_option(controls, row=10, label="Output Z",
                        values=["50 Ohm", "High-Z"], default="High-Z", width=120)

    # --- Burst --------------------------------------------------------------
    ctk.CTkLabel(controls, text="Burst", font=("", 13, "bold"),
                 anchor="w").grid(row=11, column=0, columnspan=4, padx=20,
                                  pady=(16, 4), sticky="w")
    _add_labeled_option(controls, row=12, label="Burst mode",
                        values=["Off", "N cycles", "Infinite", "Gated"],
                        default="Off", width=120)
    _add_dual_entry(controls, row=13, label_a="Cycles:", label_b="Period (s):",
                    default_a="1", default_b="0.01")
    _add_labeled_option(controls, row=14, label="Trigger source",
                        values=TRIGGER_SOURCES, default="Immediate", width=120)

    # --- Modulation (visual only for now) ---------------------------------
    ctk.CTkLabel(controls, text="Modulation (visual only)",
                 font=("", 13, "bold"), anchor="w").grid(
        row=15, column=0, columnspan=4, padx=20, pady=(16, 4), sticky="w"
    )
    _add_labeled_option(controls, row=16, label="Type",
                        values=MODULATION_OPTIONS, default="Off", width=120)
    _add_dual_entry(controls, row=17, label_a="Depth (%):", label_b="Freq (Hz):",
                    default_a="50", default_b="100")

    # --- Run / Stop --------------------------------------------------------
    ctk.CTkLabel(controls, text="Output", font=("", 13, "bold"),
                 anchor="w").grid(row=18, column=0, columnspan=4, padx=20,
                                  pady=(20, 4), sticky="w")
    btn_row = ctk.CTkFrame(controls, fg_color="transparent")
    btn_row.grid(row=19, column=0, columnspan=4, padx=20, pady=(4, 20), sticky="ew")
    btn_row.grid_columnconfigure((0, 1, 2), weight=1)
    _add_wip_button(btn_row, "Run").grid(row=0, column=0, padx=4, pady=4, sticky="ew")
    _add_wip_button(btn_row, "Stop").grid(row=0, column=1, padx=4, pady=4, sticky="ew")
    _add_wip_button(btn_row, "Apply").grid(row=0, column=2, padx=4, pady=4, sticky="ew")

    # --- Right column: empty plot placeholder -------------------------------
    plot = ctk.CTkFrame(tab)
    plot.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    plot.grid_rowconfigure(0, weight=1)
    plot.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        plot,
        text="(Plot placeholder — waveform preview will be added with the logic.)",
        text_color="#888",
    ).grid(row=0, column=0, padx=20, pady=20)
