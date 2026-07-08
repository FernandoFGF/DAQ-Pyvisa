"""
Connect tab.

A grid of instrument cards. Each card lets the user edit the
VISA address, save it to ``config.yaml``, and connect to the
instrument. On a successful connect the response to ``*IDN?`` is
displayed on the card.

The user only types the IP (e.g. ``192.168.0.32``). The
``TCPIP::`` prefix and ``::INSTR`` suffix are added automatically
on focus-out and on Return. A full address typed by the user is
preserved as-is.

Cards rendered, in order: SMU, RTA (scope1), RTO (scope2), KEY
(scope3), ArbGen, Power Supply. The actual pyvisa work lives in
:mod:`acquisition.connection`; this file is purely Tk + config.
"""

from __future__ import annotations

import re
import threading
import customtkinter as ctk


# Visual status for the per-instrument LED.
STATUS_DISCONNECTED = ("Disconnected", "#a0a0a0")
STATUS_CONNECTING = ("Connecting...", "#e0a800")
STATUS_CONNECTED = ("Connected", "#2ea043")
STATUS_ERROR = ("Error", "#d62828")

DEFAULT_CARDS = [
    # (instrument_id, short_name, description, scope_dialect)
    # ``scope_dialect`` is the legacy SCPI dialect id ("1"=RTA, "2"=RTO,
    # "3"=KEY) used by the acquisition adapters. It is None for
    # instruments that are not oscilloscopes.
    ("smu", "SMU", "Source Measure Unit", None),
    ("scope1", "RTA", "Rohde & Schwarz RTA", "1"),
    ("scope2", "RTO", "Rohde & Schwarz RTO", "2"),
    ("scope3", "KEY", "Keysight Oscilloscope", "3"),
    ("arbGen", "ArbGen", "Arbitrary Waveform Generator", None),
    ("powerSupply", "Power", "Power Supply", None),
]


def card_info(instrument_id: str):
    """Return the (id, short_name, description, dialect) tuple for a
    given instrument id, or ``None`` if not in the default list."""
    for entry in DEFAULT_CARDS:
        if entry[0] == instrument_id:
            return entry
    return None


def all_scope_instrument_ids():
    """Return the list of instrument ids that are oscilloscopes."""
    return [iid for iid, _, _, dialect in DEFAULT_CARDS if dialect is not None]

_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def normalize_address(raw: str, default_prefix: str = "TCPIP",
                      default_suffix: str = "INSTR") -> str:
    """Return a fully-qualified VISA address from whatever the user typed.

    Rules:
      * Empty / whitespace -> empty string.
      * Already contains ``::`` -> returned unchanged (preserves the
        user's explicit choice of bus / protocol / suffix).
      * Looks like a bare IPv4 (e.g. ``192.168.0.32``) -> wrapped as
        ``TCPIP::<ip>::INSTR``.
      * Anything else (e.g. ``USB0::...``, ``GPIB0::1::INSTR``) is
        returned unchanged.

    Pure function, no Tk dependency, used by both the entry widget
    and the unit tests.
    """
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""
    if "::" in text:
        return text
    if _IP_RE.match(text):
        return f"{default_prefix}::{text}::{default_suffix}"
    return text


def _address_hint_text(name: str) -> str:
    """Return the small grey hint shown under the IP entry.

    For scopes known not to enable VXI-11 RPC by default, the hint
    tells the user to type the full ``TCPIP::<ip>::5025::SOCKET``
    address instead of the auto-wrapped ``::INSTR`` form.
    """
    if name == "RTO":
        return ("RTO does not enable VXI-11 by default. Type the full "
                "address TCPIP::<ip>::5025::SOCKET to use raw-TCP SCPI.")
    if name == "RTA":
        return ("RTA accepts both VXI-11 (default ::INSTR) and raw "
                "TCP (::5025::SOCKET).")
    return "Bare IPs are auto-wrapped as TCPIP::<ip>::INSTR."


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

    addr_label = ctk.CTkLabel(addr_frame, text="IP:", width=70, anchor="w")
    addr_label.grid(row=0, column=0, padx=(0, 6))

    addr_entry = ctk.CTkEntry(addr_frame, placeholder_text="e.g. 192.168.0.32")
    addr_entry.grid(row=0, column=1, padx=(0, 6), sticky="ew")

    save_btn = ctk.CTkButton(addr_frame, text="Save", width=64,
                              command=lambda: _save_address(self, instrument_id,
                                                            addr_entry.get()))
    save_btn.grid(row=0, column=2)

    # Small grey hint under the address entry. For RTO scopes this
    # is critical: ``TCPIP::<ip>::INSTR`` triggers a VXI-11 RPC
    # probe that fails on RTO by default; the user must type the
    # full SOCKET form or pick the prefix hint.
    hint_text = _address_hint_text(name)
    addr_hint = ctk.CTkLabel(addr_frame, text=hint_text, font=("", 10),
                             text_color="#888", anchor="w", wraplength=320,
                             justify="left")
    addr_hint.grid(row=1, column=0, columnspan=3, padx=(76, 0), pady=(2, 0),
                   sticky="ew")

    # When the user leaves the entry or presses Enter, rewrite the
    # contents as a fully-qualified VISA address.
    def _finalize(_event=None):
        normalized = normalize_address(addr_entry.get())
        if normalized and normalized != addr_entry.get():
            # Only rewrite if it actually changed, to avoid clobbering
            # the cursor position while the user is typing.
            addr_entry.delete(0, "end")
            addr_entry.insert(0, normalized)

    addr_entry.bind("<FocusOut>", _finalize)
    addr_entry.bind("<Return>", _finalize)

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
        "connection": None,
        "instrument_id": instrument_id,
    }


def _set_status(widgets: dict, label: str, color: str) -> None:
    widgets["status_label"].configure(text=f"● {label}", text_color=color)


def parse_idn_model(idn: str) -> str:
    """Return the model field from a SCPI ``*IDN?`` response.

    Standard ``*IDN?`` format is::

        <manufacturer>,<model>,<serial>,<firmware>

    so the model is the chunk between the first and second comma.
    Returns an empty string if the response is empty or malformed.
    """
    if not idn:
        return ""
    parts = idn.split(",")
    if len(parts) < 2:
        return ""
    return parts[1].strip()


class CommandHistory:
    """In-memory history of SCPI commands for the command-line entry.

    Stores unique commands, most recent first. Supports arrow-key
    navigation (up = older, down = newer) and prefix-based lookup
    for autocompletion suggestions.

    The ``draft`` is the text the user was editing before they
    started scrolling through history; pressing Down past the most
    recent entry restores the draft.
    """

    def __init__(self, maxlen: int = 200) -> None:
        self._items: list[str] = []
        self._index: int = -1  # -1 means "not browsing, show draft"
        self._draft: str = ""
        self._maxlen = maxlen

    def add(self, command: str) -> None:
        command = command.strip()
        if not command:
            return
        # De-duplicate: if the command is already in the list, remove
        # the old copy so the new use moves to the top.
        if command in self._items:
            self._items.remove(command)
        self._items.insert(0, command)
        if len(self._items) > self._maxlen:
            self._items = self._items[: self._maxlen]
        # Reset browsing so the next Up starts from the top.
        self._index = -1
        self._draft = ""

    def up(self, current_text: str) -> str | None:
        """Move to an older entry. Returns the new text, or None if
        the history is empty."""
        if not self._items:
            return None
        if self._index == -1:
            # First Up: save the draft and jump to the most recent entry.
            self._draft = current_text
            self._index = 0
        elif self._index < len(self._items) - 1:
            self._index += 1
        return self._items[self._index]

    def down(self) -> str | None:
        """Move to a newer entry. Returns the new text, or None to
        signal "keep the current text untouched"."""
        if self._index == -1:
            return None
        if self._index == 0:
            # Back to the draft (what the user was editing before).
            self._index = -1
            return self._draft
        self._index -= 1
        return self._items[self._index]

    def reset(self) -> None:
        self._index = -1
        self._draft = ""

    def suggest(self, prefix: str, limit: int = 8) -> list[str]:
        """Return up to ``limit`` history entries that start with
        ``prefix`` (case-insensitive), most recent first."""
        prefix = prefix.strip()
        if not prefix:
            return []
        lc = prefix.lower()
        return [c for c in self._items if c.lower().startswith(lc)][:limit]

    def __len__(self) -> int:
        return len(self._items)


def _save_address(self, instrument_id: str, new_address: str) -> None:
    new_address = normalize_address(new_address)
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
            conn = open_pyvisa(instrument_id, self.config.config)
            idn = conn.query("*IDN?").strip()
            widgets = self.connect_cards[instrument_id]
            widgets["connection"] = conn
            widgets["idn"] = idn
            self.after(0, lambda idn=idn: _on_success(self, widgets, idn))
        except Exception as e:
            widgets = self.connect_cards[instrument_id]
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            # Bind ``e`` as a default argument so the lambda captures
            # its current value. Under Python 3.13 the ``as e`` name
            # is deleted when the ``except`` block exits, so a plain
            # ``lambda: ... str(e)`` would raise NameError later.
            self.after(0, lambda e=e: _on_error(self, widgets, str(e)))

    threading.Thread(target=_worker, daemon=True).start()


def _on_success(self, widgets: dict, idn: str) -> None:
    model = parse_idn_model(idn)
    label = f"{model}  ({idn})" if model else idn
    widgets["idn_label"].configure(text=label, text_color="#b6e3a1")
    widgets["connect_btn"].configure(state="disabled")
    widgets["disconnect_btn"].configure(state="normal")
    _set_status(widgets, *STATUS_CONNECTED)
    _refresh_command_menu(self)
    if hasattr(self, "_refresh_connected_list"):
        self._refresh_connected_list()
    # If this card is a scope, let the Spectrum and Waveform tabs
    # update their read-only scope labels and Start button states.
    info = card_info(widgets.get("instrument_id"))
    if info is not None and info[3] is not None:
        for refresh in ("_refresh_scope_label_spec", "_refresh_scope_label_wf"):
            method = getattr(self, refresh, None)
            if method is not None:
                try:
                    method()
                except Exception:
                    pass


def _on_error(self, widgets: dict, err: str) -> None:
    widgets["idn_label"].configure(text=f"Error: {err}", text_color="#ffb3b3")
    widgets["connect_btn"].configure(state="normal")
    widgets["disconnect_btn"].configure(state="disabled")
    _set_status(widgets, *STATUS_ERROR)
    widgets.pop("idn", None)
    _refresh_command_menu(self)


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
    widgets.pop("idn", None)
    idn_label.configure(text="")
    widgets["connect_btn"].configure(state="normal")
    widgets["disconnect_btn"].configure(state="disabled")
    _set_status(widgets, *STATUS_DISCONNECTED)
    print(f"[{instrument_id}] Disconnected.")
    _refresh_command_menu(self)
    if hasattr(self, "_refresh_connected_list"):
        self._refresh_connected_list()
    # If this card is a scope, let the Spectrum and Waveform tabs
    # update their read-only scope labels and disable Start.
    info = card_info(instrument_id)
    if info is not None and info[3] is not None:
        for refresh in ("_refresh_scope_label_spec", "_refresh_scope_label_wf"):
            method = getattr(self, refresh, None)
            if method is not None:
                try:
                    method()
                except Exception:
                    pass


def setting_connect(self) -> None:
    """Build the Connect tab with one card per supported instrument."""
    tab = self.tabview.tab("Connect")
    # Cards grid (row 0) and command panel (row 1).
    tab.grid_rowconfigure(0, weight=3)
    tab.grid_rowconfigure(1, weight=0)

    container = ctk.CTkFrame(tab)
    container.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
    # 3 columns x 2 rows for 6 cards.
    container.grid_columnconfigure((0, 1, 2), weight=1, uniform="card")
    container.grid_rowconfigure((0, 1), weight=1, uniform="card")

    self.connect_cards = {}
    for index, (instrument_id, name, description, _dialect) in enumerate(DEFAULT_CARDS):
        row, col = divmod(index, 3)
        widgets = _build_card(container, self, instrument_id, name, description)
        widgets["card"].grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        self.connect_cards[instrument_id] = widgets

    # --- Command line panel (under the cards) ------------------------------
    _build_command_panel(self, tab)


def _build_command_panel(self, tab: ctk.CTkFrame) -> None:
    """Inline command line for talking to connected instruments."""
    panel = ctk.CTkFrame(tab)
    panel.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
    panel.grid_columnconfigure(0, weight=0)
    panel.grid_columnconfigure(1, weight=1)
    panel.grid_columnconfigure(2, weight=0)
    panel.grid_columnconfigure(3, weight=0)

    ctk.CTkLabel(panel, text="Command line:", anchor="w").grid(
        row=0, column=0, padx=(15, 6), pady=10, sticky="w"
    )

    # Start with an empty menu; it gets filled by _refresh_command_menu
    # the first time a card connects.
    instrument_menu = ctk.CTkOptionMenu(
        panel,
        values=["(no instruments connected)"],
        dynamic_resizing=False,
        width=220,
        state="disabled",
        command=lambda _choice: _on_instrument_change(),
    )
    instrument_menu.set("(no instruments connected)")
    instrument_menu.grid(row=0, column=1, padx=(0, 6), pady=10, sticky="ew")

    cmd_entry = ctk.CTkEntry(panel, placeholder_text="SCPI command, e.g. *IDN?")
    cmd_entry.grid(row=1, column=1, padx=(0, 6), pady=(0, 10), sticky="ew")
    cmd_entry.bind(
        "<Return>",
        lambda _e: _cmd_send(self, instrument_menu, cmd_entry),
    )

    # History navigation: Up / Down arrows step through previously
    # sent commands. Each instrument has its own history so the user
    # doesn't see commands they sent to a different device.
    histories: dict[str, CommandHistory] = {}
    self.connect_command_histories = histories
    self.connect_command_history = CommandHistory()  # placeholder, swapped on change

    def _active_history() -> CommandHistory:
        iid = _selected_instrument_id(self, instrument_menu)
        if not iid:
            return self.connect_command_history
        return histories.setdefault(iid, CommandHistory())

    def _on_instrument_change() -> None:
        # When the user picks a different instrument, swap the active
        # history and clear the entry so they don't accidentally send
        # a command from another device's history.
        history = _active_history()
        self.connect_command_history = history
        cmd_entry.delete(0, "end")
        history.reset()
        suggest_menu.grid_forget()

    def _on_up(_event=None):
        new = _active_history().up(cmd_entry.get())
        if new is None:
            return "break"
        cmd_entry.delete(0, "end")
        cmd_entry.insert(0, new)
        return "break"

    def _on_down(_event=None):
        new = _active_history().down()
        if new is None:
            return "break"
        cmd_entry.delete(0, "end")
        cmd_entry.insert(0, new)
        return "break"

    # Arrow keys are normally bound to the underlying Tk entry, so
    # we re-route them here. Returning "break" prevents the default
    # behaviour (which would do nothing in a single-line entry, but
    # we want to be explicit).
    cmd_entry.bind("<Up>", _on_up)
    cmd_entry.bind("<Down>", _on_down)

    # Autocompletion dropdown: a small OptionMenu that lives just
    # under the entry. Hidden until the user presses Tab, then it
    # shows the best matches for the current prefix. Selecting one
    # copies it into the entry. Refreshing on every keystroke would
    # be jarring while typing, so we keep it explicit (Tab).
    suggest_menu = ctk.CTkOptionMenu(
        panel,
        values=[""],
        dynamic_resizing=False,
        width=220,
        command=lambda choice: _accept_suggestion(choice),
    )
    suggest_menu.set("")
    suggest_menu.grid_forget()

    def _accept_suggestion(choice: str) -> None:
        if not choice:
            return
        cmd_entry.delete(0, "end")
        cmd_entry.insert(0, choice)
        cmd_entry.icursor("end")
        suggest_menu.grid_forget()

    def _show_suggestions(_event=None):
        prefix = cmd_entry.get()
        matches = _active_history().suggest(prefix)
        if not matches:
            suggest_menu.grid_forget()
            return
        suggest_menu.configure(values=matches)
        suggest_menu.set(matches[0])
        suggest_menu.grid(
            row=2, column=1, padx=(0, 6), pady=(0, 8), sticky="ew"
        )
        return "break"  # don't let Tab move focus to the next widget

    cmd_entry.bind("<Tab>", _show_suggestions)
    cmd_entry.bind(
        "<FocusOut>",
        lambda _e: self.after(150, lambda: suggest_menu.grid_forget()),
    )

    send_btn = ctk.CTkButton(
        panel, text="Send", width=90, state="disabled",
        command=lambda: _cmd_send(self, instrument_menu, cmd_entry),
    )
    send_btn.grid(row=0, column=2, rowspan=2, padx=4, pady=10, sticky="nsew")

    query_btn = ctk.CTkButton(
        panel, text="Query", width=90, state="disabled",
        command=lambda: _cmd_query(self, instrument_menu, cmd_entry),
    )
    query_btn.grid(row=0, column=3, rowspan=2, padx=(4, 15), pady=10, sticky="nsew")

    # Stash on self so _refresh_command_menu can update it.
    self.connect_command_menu = instrument_menu
    self.connect_command_entry = cmd_entry
    self.connect_command_send_btn = send_btn
    self.connect_command_query_btn = query_btn
    self.connect_command_suggest = suggest_menu

    print("Command line ready. Connect an instrument to start sending commands.")


def _refresh_command_menu(self) -> None:
    """Rebuild the command-line instrument dropdown from currently-connected
    instruments only. No-op if the panel hasn't been built yet."""
    menu = getattr(self, "connect_command_menu", None)
    if menu is None:
        return

    connected = [
        (iid, name)
        for iid, name, _, _ in DEFAULT_CARDS
        if self.connect_cards.get(iid, {}).get("connection") is not None
    ]

    if connected:
        labels = [name for _, name in connected]
        menu.configure(values=labels, state="normal")
        # Keep the current selection if still connected; otherwise pick
        # the first available.
        try:
            current = menu.get()
        except Exception:
            current = ""
        if current not in labels:
            menu.set(labels[0])
        self.connect_command_send_btn.configure(state="normal")
        self.connect_command_query_btn.configure(state="normal")
    else:
        menu.configure(values=["(no instruments connected)"], state="disabled")
        menu.set("(no instruments connected)")
        self.connect_command_send_btn.configure(state="disabled")
        self.connect_command_query_btn.configure(state="disabled")


def _selected_instrument_id(self, instrument_menu) -> str:
    """Resolve the currently shown label on the menu to an instrument id."""
    try:
        current = instrument_menu.get()
    except Exception:
        return ""
    for entry in DEFAULT_CARDS:
        instrument_id = entry[0]
        name = entry[1] if len(entry) > 1 else instrument_id
        if name == current:
            return instrument_id
    return ""


def _cmd_send(self, instrument_menu, cmd_entry) -> None:
    raw = cmd_entry.get().strip()
    instrument_id = _selected_instrument_id(self, instrument_menu)
    if not instrument_id:
        print("No instrument connected. Connect one in the cards above.")
        return
    if not raw:
        print("Nothing to send.")
        return
    conn = self.connect_cards.get(instrument_id, {}).get("connection")
    if conn is None:
        print(f"[{instrument_id}] Not connected.")
        return
    print(f"[{instrument_id}] >> {raw}")
    _push_history(self, instrument_id, raw)

    def _worker():
        try:
            conn.write(raw)
            self.after(0, lambda: print(f"[{instrument_id}] OK"))
        except Exception as e:
            self.after(0, lambda err=e: print(f"[{instrument_id}] Error: {err}"))

    threading.Thread(target=_worker, daemon=True).start()
    cmd_entry.delete(0, "end")
    _hide_suggestions(self)


def _cmd_query(self, instrument_menu, cmd_entry) -> None:
    raw = cmd_entry.get().strip()
    instrument_id = _selected_instrument_id(self, instrument_menu)
    if not instrument_id:
        print("No instrument connected. Connect one in the cards above.")
        return
    if not raw:
        print("Nothing to send.")
        return
    conn = self.connect_cards.get(instrument_id, {}).get("connection")
    if conn is None:
        print(f"[{instrument_id}] Not connected.")
        return
    print(f"[{instrument_id}] ?< {raw}")
    _push_history(self, instrument_id, raw)

    def _worker():
        try:
            response = conn.query(raw)
            text = response if response else "(empty response)"
            self.after(0, lambda t=text: print(f"[{instrument_id}] < {t}"))
        except Exception as e:
            self.after(0, lambda err=e: print(f"[{instrument_id}] Error: {err}"))

    threading.Thread(target=_worker, daemon=True).start()
    cmd_entry.delete(0, "end")
    _hide_suggestions(self)


def _push_history(self, instrument_id: str, raw: str) -> None:
    histories = getattr(self, "connect_command_histories", None)
    if not histories:
        return
    history = histories.get(instrument_id)
    if history is None:
        history = CommandHistory()
        histories[instrument_id] = history
    history.add(raw)
    # Keep the cached reference in sync so the entry's Up/Down
    # handlers see the latest command without a round-trip through
    # the instrument_menu callback.
    self.connect_command_history = history


def _hide_suggestions(self) -> None:
    menu = getattr(self, "connect_command_suggest", None)
    if menu is not None:
        try:
            menu.grid_forget()
        except Exception:
            pass


def _cmd_query(self, instrument_menu, cmd_entry) -> None:
    raw = cmd_entry.get().strip()
    instrument_id = _selected_instrument_id(self, instrument_menu)
    if not instrument_id:
        print("No instrument connected. Connect one in the cards above.")
        return
    if not raw:
        print("Nothing to send.")
        return
    conn = self.connect_cards.get(instrument_id, {}).get("connection")
    if conn is None:
        print(f"[{instrument_id}] Not connected.")
        return
    print(f"[{instrument_id}] ?< {raw}")

    def _worker():
        try:
            response = conn.query(raw)
            text = response if response else "(empty response)"
            self.after(0, lambda t=text: print(f"[{instrument_id}] < {t}"))
        except Exception as e:
            self.after(0, lambda err=e: print(f"[{instrument_id}] Error: {err}"))

    threading.Thread(target=_worker, daemon=True).start()
    cmd_entry.delete(0, "end")
