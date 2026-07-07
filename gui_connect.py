"""
Connect tab.

A 2x2 grid of instrument cards: SMU, RTA (scope1), RTO (scope2),
KEY (scope3). Each card lets the user edit the VISA address, save it
to ``config.yaml``, and connect to the instrument. On a successful
connect the response to ``*IDN?`` is displayed on the card.

The actual pyvisa work happens in :mod:`acquisition.connection`; this
file is purely Tk and config-driven.
"""

from __future__ import annotations

import threading
import customtkinter as ctk


# Visual status for the per-instrument LED.
STATUS_DISCONNECTED = ("Disconnected", "#a0a0a0")
STATUS_CONNECTING = ("Connecting...", "#e0a800")
STATUS_CONNECTED = ("Connected", "#2ea043")
STATUS_ERROR = ("Error", "#d62828")

# Cards rendered in this order. The first entry is the SMU; the other
# three are oscilloscopes in the order they appear in config.yaml.
DEFAULT_CARDS = [
    ("smu", "SMU", "Source Measure Unit"),
    ("scope1", "RTA", "Rohde & Schwarz RTA"),
    ("scope2", "RTO", "Rohde & Schwarz RTO"),
    ("scope3", "KEY", "Keysight Oscilloscope"),
]


def _build_card(parent: ctk.CTkFrame, self, instrument_id: str, name: str,
                description: str) -> dict:
    """Build a single instrument card. Returns a dict of widgets to keep."""
    card = ctk.CTkFrame(parent, corner_radius=10, border_width=1)
    card.grid_columnconfigure(0, weight=1)

    title = ctk.CTkLabel(card, text=f"{name}", font=("", 16, "bold"), anchor="w")
    title.grid(row=0, column=0, padx=15, pady=(12, 0), sticky="ew")

    subtitle = ctk.CTkLabel(card, text=description, font=("", 11), anchor="w",
                            text_color="#888")
    subtitle.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="ew")

    addr_frame = ctk.CTkFrame(card, fg_color="transparent")
    addr_frame.grid(row=2, column=0, padx=15, pady=(4, 4), sticky="ew")
    addr_frame.grid_columnconfigure(1, weight=1)

    addr_label = ctk.CTkLabel(addr_frame, text="Address:", width=70, anchor="w")
    addr_label.grid(row=0, column=0, padx=(0, 6))

    addr_entry = ctk.CTkEntry(addr_frame, placeholder_text="TCPIP::x.x.x.x::INSTR")
    addr_entry.grid(row=0, column=1, padx=(0, 6), sticky="ew")

    save_btn = ctk.CTkButton(addr_frame, text="Save", width=64,
                              command=lambda: _save_address(self, instrument_id,
                                                            addr_entry.get()))
    save_btn.grid(row=0, column=2)

    idn_label = ctk.CTkLabel(card, text="", font=("", 11), anchor="w",
                              text_color="#bbb", wraplength=320, justify="left")
    idn_label.grid(row=3, column=0, padx=15, pady=(4, 8), sticky="ew")

    btn_frame = ctk.CTkFrame(card, fg_color="transparent")
    btn_frame.grid(row=4, column=0, padx=15, pady=(4, 12), sticky="ew")
    btn_frame.grid_columnconfigure(0, weight=1)
    btn_frame.grid_columnconfigure(1, weight=1)

    connect_btn = ctk.CTkButton(btn_frame, text="Connect",
                                 command=lambda: _do_connect(self, instrument_id,
                                                             idn_label, connect_btn,
                                                             disconnect_btn, status_label))
    connect_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

    disconnect_btn = ctk.CTkButton(btn_frame, text="Disconnect", state="disabled",
                                    command=lambda: _do_disconnect(self, instrument_id,
                                                                   idn_label, connect_btn,
                                                                   disconnect_btn,
                                                                   status_label))
    disconnect_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    status_label = ctk.CTkLabel(card, text=f"● {STATUS_DISCONNECTED[0]}",
                                 font=("", 11), anchor="w", text_color=STATUS_DISCONNECTED[1])
    status_label.grid(row=5, column=0, padx=15, pady=(0, 10), sticky="ew")

    # Initial population of the address from config. Be tolerant: if the
    # instrument is missing from the YAML (e.g. a fresh checkout with a
    # partial config), the card still renders with an empty address field
    # instead of crashing the whole app.
    try:
        current = self.config.get_instrument_address(instrument_id)
    except KeyError:
        current = ""
    except Exception:
        current = ""
    if current:
        addr_entry.insert(0, current)

    return {
        "card": card,
        "addr_entry": addr_entry,
        "idn_label": idn_label,
        "connect_btn": connect_btn,
        "disconnect_btn": disconnect_btn,
        "status_label": status_label,
        "connection": None,  # the live InstrumentConnection, if any
    }


def _set_status(widgets: dict, label: str, color: str) -> None:
    widgets["status_label"].configure(text=f"● {label}", text_color=color)


def _save_address(self, instrument_id: str, new_address: str) -> None:
    new_address = (new_address or "").strip()
    if not new_address:
        print(f"[{instrument_id}] Address cannot be empty.")
        return
    try:
        self.config.set_instrument_address(instrument_id, new_address)
    except KeyError:
        print(f"[{instrument_id}] Not in config.yaml; cannot save.")
        return
    except Exception as e:
        print(f"[{instrument_id}] Failed to save address: {e}")
        return
    print(f"[{instrument_id}] Address saved: {new_address}")


def _do_connect(self, instrument_id: str, idn_label, connect_btn,
                disconnect_btn, status_label) -> None:
    widgets = self.connect_cards[instrument_id]
    widgets["connect_btn"].configure(state="disabled")
    widgets["disconnect_btn"].configure(state="disabled")
    _set_status(widgets, *STATUS_CONNECTING)
    idn_label.configure(text="Opening connection and querying *IDN? ...")

    def _worker():
        from acquisition.connection import open_pyvisa
        conn = None
        try:
            # Tolerate a missing instrument: a placeholder address still
            # lets us render a "no address configured" error in the UI
            # instead of crashing the worker thread.
            conn = open_pyvisa(instrument_id, self.config.config)
            idn = conn.query("*IDN?").strip()
            widgets = self.connect_cards[instrument_id]
            widgets["connection"] = conn
            self.after(0, lambda: _on_success(widgets, idn))
        except Exception as e:
            widgets = self.connect_cards[instrument_id]
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            self.after(0, lambda: _on_error(widgets, str(e)))

    threading.Thread(target=_worker, daemon=True).start()


def _on_success(widgets: dict, idn: str) -> None:
    widgets["idn_label"].configure(text=f"*IDN? -> {idn}", text_color="#b6e3a1")
    widgets["connect_btn"].configure(state="disabled")
    widgets["disconnect_btn"].configure(state="normal")
    _set_status(widgets, *STATUS_CONNECTED)


def _on_error(widgets: dict, err: str) -> None:
    widgets["idn_label"].configure(text=f"Error: {err}", text_color="#ffb3b3")
    widgets["connect_btn"].configure(state="normal")
    widgets["disconnect_btn"].configure(state="disabled")
    _set_status(widgets, *STATUS_ERROR)


def _do_disconnect(self, instrument_id: str, idn_label, connect_btn,
                   disconnect_btn, status_label) -> None:
    widgets = self.connect_cards[instrument_id]
    conn = widgets.get("connection")
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    widgets["connection"] = None
    idn_label.configure(text="")
    widgets["connect_btn"].configure(state="normal")
    widgets["disconnect_btn"].configure(state="disabled")
    _set_status(widgets, *STATUS_DISCONNECTED)
    print(f"[{instrument_id}] Disconnected.")


def setting_connect(self) -> None:
    """Build the Connect tab with one card per supported instrument."""
    container = ctk.CTkFrame(self.tabview.tab("Connect"))
    container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
    container.grid_columnconfigure((0, 1), weight=1, uniform="card")
    container.grid_rowconfigure((0, 1), weight=1, uniform="card")

    self.connect_cards = {}
    for index, (instrument_id, name, description) in enumerate(DEFAULT_CARDS):
        row, col = divmod(index, 2)
        widgets = _build_card(container, self, instrument_id, name, description)
        widgets["card"].grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        self.connect_cards[instrument_id] = widgets
