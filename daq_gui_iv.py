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

    self.options = ctk.CTkOptionMenu(self.optionsIV,
                                    dynamic_resizing=False, values=["SMU", "Classic"])
    self.options.grid(row=0, column=0, padx=20, pady=(20, 0))

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
    self.vStep.grid(row=6, column=0, padx=20, pady=(0,20))

    self.start_button = ctk.CTkButton(self.optionsIV, text="Start", command=self.start_iv)
    self.start_button.grid(row=7, column=0, padx=20, pady=(10,20), columnspan=2, sticky="s")

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
