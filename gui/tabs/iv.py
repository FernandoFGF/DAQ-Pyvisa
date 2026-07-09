"""
Módulo que contiene la interfaz gráfica para las curvas IV.

Las acciones de análisis (Vbr, Qr, "Draw complete") delegan en
``analysis.iv_analysis``. Las mediciones de adquisición se hacen a
través de ``DAQGUIFunctions.start_iv_full`` (ver daq_gui_main.py).
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


def _do_vbr(self):
    from analysis.iv_analysis import calculate_vbr
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    result = calculate_vbr(v, i)
    if not result["ok"]:
        print(result["message"])
        return
    self.vbr_Output.configure(state="normal")
    self.vbr_Output.delete("1.0", "end")
    self.vbr_Output.insert("0.0", f"{result['max_x']} V")
    self.vbr_Output.configure(state="disabled")

    fig = self.canvas.figure
    self.canvas.draw()
    ax = fig.gca()
    self.gui_funcs.plot_iv(
        ax,
        result["v_filtered"],
        result["i_filtered"],
        vbr_point=(result["max_x"], result["max_y"]),
        dydx_over_y=result["dydx_over_y"],
        v_for_ratio=result["v_for_ratio"],
    )


def _do_qr(self):
    from analysis.iv_analysis import calculate_qr
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    result = calculate_qr(v, i)
    if not result["ok"]:
        print(result["message"])
        return
    self.qr_Output.configure(state="normal")
    self.qr_Output.delete("1.0", "end")
    self.qr_Output.insert("0.0", f"{result['qr_value']} Ω")
    self.qr_Output.configure(state="disabled")

    fig = self.canvas.figure
    self.canvas.draw()
    ax = fig.gca()
    self.gui_funcs.plot_iv(
        ax,
        result["v_positive"],
        result["i_positive"],
        qr_line=(result["v_fit"], result["i_fit"]),
    )


def _do_complete(self):
    v, i = _parse_iv_aux(self)
    if v is None:
        print("Necesitas realizar algun analisis primero..")
        return
    fig = self.canvas.figure
    self.canvas.draw()
    ax = fig.gca()
    self.gui_funcs.plot_iv(ax, v, i)


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
    """Make the channel check boxes mutually exclusive.

    Picking a channel clears the other one so the SMU is
    always driven on exactly one channel. The Keithley 2470
    commands (``(@1)`` / ``(@2)``) follow the SMU channel
    numbering; we surface that in the GUI as well.
    """
    var_ch1 = getattr(self, "iv_channel_var_ch1", None)
    var_ch2 = getattr(self, "iv_channel_var_ch2", None)
    if var_ch1 is None or var_ch2 is None:
        return
    if channel == 1 and var_ch1.get():
        var_ch2.set(False)
    elif channel == 2 and var_ch2.get():
        var_ch1.set(False)
    else:
        # The user unchecked the only selected channel. Force
        # channel 1 back on so the SMU always has a target.
        if not var_ch1.get() and not var_ch2.get():
            var_ch1.set(True)


def iv_selected_channel(self) -> int:
    """Return the SMU channel the user selected (1 or 2).

    Defaults to 1 when the check boxes are in an unexpected
    state. The value is passed to the adapter as
    ``channel=...`` and substituted into the ``(@N)`` token
    of the :FETCh:ARR:CURR? and :init queries.
    """
    var_ch1 = getattr(self, "iv_channel_var_ch1", None)
    var_ch2 = getattr(self, "iv_channel_var_ch2", None)
    if var_ch1 is None or var_ch2 is None:
        return 1
    return 2 if var_ch2.get() else 1


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

    self.iv_start = ctk.CTkLabel(self.optionsIV, text="Set voltage start:", anchor="w")
    self.iv_start.grid(row=1, column=0, padx=20, pady=(10, 0))
    self.vStart = ctk.CTkEntry(self.optionsIV, placeholder_text="1V defalut")
    self.vStart.grid(row=2, column=0, padx=20, pady=(0,5))

    self.iv_stop = ctk.CTkLabel(self.optionsIV, text="Set voltage stop:", anchor="w")
    self.iv_stop.grid(row=3, column=0, padx=20, pady=(5, 0))
    self.vStop = ctk.CTkEntry(self.optionsIV, placeholder_text="-40V defalut")
    self.vStop.grid(row=4, column=0, padx=20, pady=(0,5))

    self.iv_step = ctk.CTkLabel(self.optionsIV, text="Set voltage step:", anchor="w")
    self.iv_step.grid(row=5, column=0, padx=20, pady=(5, 0))
    self.vStep = ctk.CTkEntry(self.optionsIV, placeholder_text="0.05V defalut")
    self.vStep.grid(row=6, column=0, padx=20, pady=(0,5))

    # Channel selector. The Keithley 2470 has two channels; we
    # let the user pick which one to drive with a pair of
    # mutually-exclusive check boxes. They sit on the same row
    # as the vStep entry so the whole parameters column stays
    # aligned, and there is no "Channel:" label.
    self.iv_channel_var_ch1 = ctk.BooleanVar(value=True)
    self.iv_channel_var_ch2 = ctk.BooleanVar(value=False)
    self.iv_channel_ch1 = ctk.CTkCheckBox(
        self.optionsIV, text="CH1", variable=self.iv_channel_var_ch1,
        command=lambda: _iv_on_channel_toggle(self, 1),
    )
    self.iv_channel_ch1.grid(row=6, column=1, padx=(0, 12), pady=(0, 5), sticky="w")
    self.iv_channel_ch2 = ctk.CTkCheckBox(
        self.optionsIV, text="CH2", variable=self.iv_channel_var_ch2,
        command=lambda: _iv_on_channel_toggle(self, 2),
    )
    self.iv_channel_ch2.grid(row=6, column=1, padx=(60, 0), pady=(0, 5), sticky="w")

    self.start_button = ctk.CTkButton(self.optionsIV, text="Start", command=self.start_iv)
    self.start_button.grid(row=7, column=0, padx=20, pady=(15, 20), columnspan=2, sticky="s")

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

    self.qr_button = ctk.CTkButton(self.analysisIV, text="Calculate Qr", command=lambda: _do_qr(self), width=120)
    self.qr_button.grid(row=2, column=0, padx=(10), pady=(10,5))
    self.qr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.qr_Output.grid(row=3, column=0, padx=(10), pady=(5,5))

    self.complete_button = ctk.CTkButton(self.analysisIV, text="Draw complete", command=lambda: _do_complete(self), width=120)
    self.complete_button.grid(row=4, column=0, padx=(10), pady=(20,5))
