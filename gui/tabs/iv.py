"""
Módulo que contiene la interfaz gráfica para las curvas IV.

Las acciones de análisis (Vbr, Qr, "Draw complete") delegan en
``analysis.iv_analysis``. Las mediciones de adquisición se hacen a
través de ``DAQGUIFunctions.start_iv_full`` (ver daq_gui_main.py).

Analysis behaviour:

  * **Vbr** plots the negative section of the IV curve with
    the (dI/dV)/I derivative on a secondary y-axis (red), and
    marks the calculated Vbr point on both the IV curve and
    the derivative minimum.

  * **Qr** plots the positive section of the IV curve with a
    linear fit between two user-defined voltage endpoints.
    The user enters the start and end voltages in the text
    inputs and clicks Qr; the fit is computed immediately
    between the nearest data points.

  * **Draw complete** plots the full IV curve so the user
    sees the whole SiPM response (positive + negative).
"""
import customtkinter as ctk


def _parse_iv_aux(self):
    v_str = self.v_values_aux.get()
    i_str = self.i_values_aux.get()
    if not v_str or not i_str:
        return None, None
    v = [float(x) for x in v_str.split(", ")]
    i = [float(x) for x in i_str.split(", ")]
    return v, i


def _get_canvas(self):
    """Return (figure, axes) for the IV plot.

    The Vbr plot helper creates a twinx (secondary y-axis
    for the derivative). After that call, ``fig.gca()``
    returns the twinx instead of the primary axes, and any
    subsequent plot on that axes is hidden from the user's
    view. We pick the primary axes explicitly: the one
    whose ``get_twinx`` has not been used to spawn a
    sibling (a twinx is always the *secondary* axes that
    appears later in ``fig.axes``; the original is the
    first one). We look for the axes whose ylabel is the
    primary one ('Amperios') which the Vbr / QR / Complete
    helpers always set; if no axes matches, we fall back
    to the first axes in the figure.
    """
    fig = self.canvas.figure
    for candidate in fig.axes:
        if candidate.get_ylabel() == "Amperios":
            return fig, candidate
    # Fallback: pick the first axes.
    if fig.axes:
        return fig, fig.axes[0]
    return fig, fig.gca()


def _do_vbr(self):
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    result = self.gui_funcs.vbr_for(v, i)
    if not result["ok"]:
        print(result["message"])
        return
    self.vbr_Output.configure(state="normal")
    self.vbr_Output.delete("1.0", "end")
    self.vbr_Output.insert("0.0", f"{result['max_x']:.4g} V")
    self.vbr_Output.configure(state="disabled")

    # Remember the Vbr point so ``_do_complete`` can keep
    # the red dot on the negative section when the user
    # switches to the full-curve view.
    self.iv_vbr_point = (result["max_x"], result["max_y"])

    _, ax = _get_canvas(self)
    self.gui_funcs.plot_vbr(
        ax,
        v_filtered=result["v_filtered"],
        i_filtered=result["i_filtered"],
        vbr_point=(result["max_x"], result["max_y"]),
        dydx_over_y=result["dydx_over_y"],
        v_for_ratio=result["v_for_ratio"],
    )
    try:
        self.canvas.draw()
        self.canvas.flush_events()
    except Exception:
        pass


def _do_qr(self):
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return

    try:
        v1 = float(self.qr_v1_entry.get().strip() or "0.1")
        v2 = float(self.qr_v2_entry.get().strip() or "0.2")
    except ValueError:
        print("Los valores de QR deben ser números válidos.")
        return

    if v1 >= v2:
        print("QR V start debe ser menor que QR V end.")
        return

    _, ax = _get_canvas(self)
    result = self.gui_funcs.qr_for(v, i, v_range=(v1, v2))
    if not result["ok"]:
        print(result["message"])
        return
    self.qr_Output.configure(state="normal")
    self.qr_Output.delete("1.0", "end")
    self.qr_Output.insert("0.0", f"{result['qr_value']} Ω")
    self.qr_Output.configure(state="disabled")
    self.gui_funcs.plot_qr_with_fit(
        ax, result["v_positive"], result["i_positive"],
        result["v_fit"], result["i_fit"],
    )
    try:
        self.canvas.draw()
        self.canvas.flush_events()
    except Exception:
        pass


def _do_complete(self):
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    _, ax = _get_canvas(self)
    vbr_point = getattr(self, "iv_vbr_point", None)
    self.gui_funcs.plot_complete(ax, v, i, vbr_point=vbr_point)
    try:
        self.canvas.draw()
        self.canvas.flush_events()
    except Exception:
        pass


def _reset_qr_state(self) -> None:
    self.iv_vbr_point = None


def iv_update_connected(self) -> None:
    """Re-read the SMU connection and repaint the IV tab header.

    Called from the Connect tab success / disconnect handlers
    so the "SMU: <*IDN?>" line always reflects the live
    state. When no SMU is connected the line shows a grey
    placeholder and the Start button is disabled.
    """
    label = getattr(self, "iv_smu_label", None)
    if label is None:
        return
    card = (self.connect_cards.get("smu")
            if isinstance(getattr(self, "connect_cards", None), dict) else None)
    conn = card.get("connection") if isinstance(card, dict) else None
    idn = card.get("idn") if isinstance(card, dict) else None
    if conn is not None and idn:
        label.configure(
            text=f"SMU: {idn}", text_color="#2ea043",
        )
    else:
        label.configure(
            text="SMU: (not connected)", text_color="#a0a0a0",
        )


def _iv_on_channel_toggle(self, channel: int) -> None:
    """No-op kept for back-compat with the old check-box API.

    The radio buttons share a single StringVar, so the
    selection is automatically mutually exclusive and we
    never need to clear the other option. The argument is
    ignored; the helper is referenced from the old test
    suite and from any external code that may have wired
    the legacy check-box command callback.
    """
    return None


def iv_selected_channel(self) -> int:
    """Return the SMU channel the user selected (1 or 2).

    Reads the radio-button StringVar. Defaults to 1 when
    the radio group has not been built yet (older App
    instances that predate the radio refactor) or when
    the value is unexpected. The returned integer is passed
    to the adapter as ``channel=...`` and substituted into
    the ``(@N)`` token of the :init and :FETCh commands.
    """
    var = getattr(self, "selected_channelIV", None)
    if var is None:
        return 1
    return 2 if var.get() == "CH2" else 1


def setting_iv(self):
    """
    Construye la pestaña IV Curves (DAQ + Analysis).
    """
    # create tabview
    self.tabviewIV = ctk.CTkTabview(self.tabview.tab("IV Curves"), width=100)
    self.tabviewIV.grid(row=0, column=0, padx=(5, 5), pady=(5, 5), sticky="nsew")
    self.tabviewIV.add("DAQ")
    self.tabviewIV.add("Analysis")
    self.tabviewIV.tab("DAQ").grid_columnconfigure(0, weight=0)
    self.tabviewIV.tab("DAQ").grid_columnconfigure(1, weight=3)
    self.tabviewIV.tab("DAQ").grid_rowconfigure(0, weight=1)
    self.tabviewIV.tab("Analysis").grid_columnconfigure(0, weight=0)
    self.tabviewIV.tab("Analysis").grid_columnconfigure(1, weight=3)
    self.tabviewIV.tab("Analysis").grid_rowconfigure(0, weight=1)

    # IV Curves tab settings DAQ
    self.optionsIV = ctk.CTkFrame(self.tabviewIV.tab("DAQ"))
    self.optionsIV.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    self.optionsIV.grid_columnconfigure((0, 1), weight=1)

    # The legacy SMU / Classic selector was removed; the SMU
    # card in the Connect tab is now the only way to choose the
    # source. We show the raw ``*IDN?`` of the connected SMU
    # (or a placeholder) so the user always knows which
    # instrument will be driven when they press Start.
    self.iv_smu_label = ctk.CTkLabel(
        self.optionsIV, text="SMU: (not connected)",
        anchor="w", font=("", 12, "bold"), text_color="#a0a0a0",
    )
    self.iv_smu_label.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
    # Back-compat attribute: legacy code paths and tests still
    # read ``self.options.get()`` to decide what to do. There
    # is no other SMU path today, so we hard-code "SMU".
    self.options = ctk.CTkOptionMenu(
        self.optionsIV, dynamic_resizing=False, values=["SMU"],
    )
    self.options.set("SMU")
    self.options.grid(row=0, column=1, padx=20, pady=(20, 0))
    self.options.grid_remove()

    # Channel selector. The Keithley 2470 has two channels; we
    # let the user pick which one to drive. Mirrors the
    # Spectrum / Waveform layout: an opaque box with two
    # columns, each column holding one CTkRadioButton. Both
    # columns have weight=1 so the radios sit centred in
    # their respective cells, regardless of the optionsIV
    # width. The radios share a single StringVar so mutual
    # exclusion comes for free.
    self.selected_channelIV = ctk.StringVar(value="CH1")
    self.channels_frame_iv = ctk.CTkFrame(self.optionsIV)
    self.channels_frame_iv.grid(
        row=1, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="ew",
    )
    # Two equal-weight columns so the two radios end up
    # horizontally centred within the box (each radio
    # sits in the middle of its own cell).
    self.channels_frame_iv.grid_columnconfigure((0, 1), weight=1)
    self.ch1IV = ctk.CTkRadioButton(
        self.channels_frame_iv, text="CH1",
        variable=self.selected_channelIV, value="CH1",
    )
    self.ch1IV.grid(row=0, column=0, padx=0, pady=(10, 5))
    self.ch2IV = ctk.CTkRadioButton(
        self.channels_frame_iv, text="CH2",
        variable=self.selected_channelIV, value="CH2",
    )
    self.ch2IV.grid(row=0, column=1, padx=0, pady=(10, 5))

    self.iv_start = ctk.CTkLabel(self.optionsIV, text="Set voltage start:", anchor="w")
    self.iv_start.grid(row=2, column=0, padx=20, pady=(10, 0), columnspan=2, sticky="w")
    self.vStart = ctk.CTkEntry(self.optionsIV, placeholder_text="1V defalut")
    self.vStart.grid(row=3, column=0, padx=20, pady=(0,5), columnspan=2, sticky="ew")

    self.iv_stop = ctk.CTkLabel(self.optionsIV, text="Set voltage stop:", anchor="w")
    self.iv_stop.grid(row=4, column=0, padx=20, pady=(5, 0), columnspan=2, sticky="w")
    self.vStop = ctk.CTkEntry(self.optionsIV, placeholder_text="-40V defalut")
    self.vStop.grid(row=5, column=0, padx=20, pady=(0,5), columnspan=2, sticky="ew")

    self.iv_step = ctk.CTkLabel(self.optionsIV, text="Set voltage step:", anchor="w")
    self.iv_step.grid(row=6, column=0, padx=20, pady=(5, 0), columnspan=2, sticky="w")
    self.vStep = ctk.CTkEntry(self.optionsIV, placeholder_text="0.05V defalut")
    self.vStep.grid(row=7, column=0, padx=20, pady=(0,5), columnspan=2, sticky="ew")

    self.start_button = ctk.CTkButton(self.optionsIV, text="Start", command=self.start_iv)
    self.start_button.grid(row=8, column=0, padx=20, pady=(15, 20), columnspan=2, sticky="s")

    # QR drag state and cached Vbr point.
    _reset_qr_state(self)

    self.plotIV = ctk.CTkFrame(self.tabview.tab("IV Curves"))
    self.plotIV.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    self.plotIV.grid_rowconfigure(0, weight=1)
    self.plotIV.grid_columnconfigure(0, weight=1)

    # Analysis tab
    self.analysisIV = ctk.CTkFrame(self.tabviewIV.tab("Analysis"))
    self.analysisIV.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    self.vbr_button = ctk.CTkButton(self.analysisIV, text="Calculate Vbr", command=lambda: _do_vbr(self), width=120)
    self.vbr_button.grid(row=0, column=0, padx=(10), pady=(20,5))
    self.vbr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.vbr_Output.grid(row=1, column=0, padx=(10), pady=(5,10))

    ctk.CTkLabel(self.analysisIV, text="QR V start:", anchor="w").grid(
        row=2, column=0, padx=(10), pady=(5, 0), sticky="w")
    self.qr_v1_entry = ctk.CTkEntry(self.analysisIV, width=100, placeholder_text="0.1")
    self.qr_v1_entry.grid(row=3, column=0, padx=(10), pady=(0, 5))
    self.qr_v1_entry.insert(0, "0.1")

    ctk.CTkLabel(self.analysisIV, text="QR V end:", anchor="w").grid(
        row=4, column=0, padx=(10), pady=(5, 0), sticky="w")
    self.qr_v2_entry = ctk.CTkEntry(self.analysisIV, width=100, placeholder_text="0.2")
    self.qr_v2_entry.grid(row=5, column=0, padx=(10), pady=(0, 5))
    self.qr_v2_entry.insert(0, "0.2")

    self.qr_button = ctk.CTkButton(self.analysisIV, text="Calculate Qr", command=lambda: _do_qr(self), width=120)
    self.qr_button.grid(row=6, column=0, padx=(10), pady=(10,5))
    self.qr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.qr_Output.grid(row=7, column=0, padx=(10), pady=(5,5))

    self.complete_button = ctk.CTkButton(self.analysisIV, text="Draw complete", command=lambda: _do_complete(self), width=120)
    self.complete_button.grid(row=8, column=0, padx=(10), pady=(20,5))
