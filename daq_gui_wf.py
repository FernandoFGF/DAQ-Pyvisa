"""
Module for the SiPMs UGR DAQ waveform functionality.

DAQ Start is wired in ``daq_gui_main.py`` to
``DAQGUIFunctions.start_waveform_full``. The Analysis tab (DCR + slider
+ - buttons) delegates to ``analysis.waveform_analysis``.
"""
import customtkinter as ctk
import os


def _load_and_plot_waveform(self, file_index: int):
    path = str(self.path_wf.get())
    name = self.save_entry.get()
    if not path or not name:
        return
    file_path = os.path.join(path, f"{name}_{int(round(file_index))}.txt")
    if not os.path.exists(file_path):
        print(f"Fichero no encontrado: {file_path}")
        return
    data = self.gui_funcs.load_waveform_file(file_path)
    num_points = int(self.num_points.get()) if self.num_points.get() else len(data)
    self.gui_funcs.plot_waveform(self.ax, data, num_points=num_points)


def _do_dcr(self):
    path = str(self.path_wf.get())
    name = self.save_entry.get()
    if not path or not name:
        self.dcr_output.configure(state="normal")
        self.dcr_output.delete("1.0", "end")
        self.dcr_output.insert("0.0", "N/A")
        self.dcr_output.configure(state="disabled")
        return
    count, time_line = self.gui_funcs.count_waveform_files(path, name)
    result = self.gui_funcs.calculate_dcr(count, time_line)
    self.dcr_output.configure(state="normal")
    self.dcr_output.delete("1.0", "end")
    if result["ok"]:
        self.dcr_output.insert("0.0", f"{result['dcr_value']} Hz")
    else:
        print("Error al calcular el dcr:", result["error"])
        self.dcr_output.insert("0.0", "Error")
    self.dcr_output.configure(state="disabled")


def _slider_event(self, value):
    print("Fichero n: " + str(round(value)))
    _load_and_plot_waveform(self, round(value))


def _decrease_slider_value(self):
    current = round(self.slider_wf.get())
    if current > 0:
        new = current - 1
        self.slider_wf.set(new)
        _load_and_plot_waveform(self, new)


def _increase_slider_value(self):
    current = round(self.slider_wf.get())
    count, _ = self.gui_funcs.count_waveform_files(
        str(self.path_wf.get()), self.save_entry.get()
    )
    if current < count:
        new = current + 1
        self.slider_wf.set(new)
        _load_and_plot_waveform(self, new)


def setting_wf(self):
    """
    Configure the settings for the Waveform tab in the SiPMs UGR DAQ application.
    """
    self.tabviewWf = ctk.CTkTabview(self.tabview.tab("Waveform"), width=100)
    self.tabviewWf.grid(row=0, column=0, padx=(5, 5), pady=(5, 5), sticky="nsew")
    self.tabviewWf.add("DAQ")
    self.tabviewWf.add("Analysis")
    self.tabviewWf.tab("DAQ").grid_columnconfigure(0, weight=0)
    self.tabviewWf.tab("DAQ").grid_columnconfigure(1, weight=3)
    self.tabviewWf.tab("DAQ").grid_rowconfigure(0, weight=1)
    self.tabviewWf.tab("Analysis").grid_columnconfigure(0, weight=0)
    self.tabviewWf.tab("Analysis").grid_columnconfigure(1, weight=3)
    self.tabviewWf.tab("Analysis").grid_rowconfigure(0, weight=1)

    self.optionsWf = ctk.CTkFrame(self.tabviewWf.tab("DAQ"))
    self.optionsWf.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    self.optionsWf.grid_rowconfigure(4, weight=1)
    self.optionsWf.columnconfigure(0, weight=1)
    self.optionsWf.columnconfigure(1, weight=1)

    self.timeWfLabel = ctk.CTkLabel(self.optionsWf, text="Set time to acquire:", anchor="w")
    self.timeWfLabel.grid(row=0, column=0, padx=10, pady=(20, 0), columnspan=2)
    self.timeWf = ctk.CTkEntry(self.optionsWf, placeholder_text="Default inmediatly")
    self.timeWf.grid(row=1, column=0, padx=10, pady=(0,0), columnspan=2)

    self.selected_channelWf = ctk.StringVar(value="1")
    self.selected_scopeWf = ctk.StringVar(value="1")

    self.scopes_frame_wf = ctk.CTkFrame(self.optionsWf)
    self.scopes_frame_wf.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    self.scope1Wf = ctk.CTkRadioButton(self.scopes_frame_wf, text="RTA", variable=self.selected_scopeWf, value="1")
    self.scope1Wf.grid(row=0, column=0, padx=(10, 5), pady=(10, 5))

    self.scope2Wf = ctk.CTkRadioButton(self.scopes_frame_wf, text="RTO", variable=self.selected_scopeWf, value="2")
    self.scope2Wf.grid(row=0, column=1, padx=(5, 10), pady=(10, 5))

    self.scope3Wf = ctk.CTkRadioButton(self.scopes_frame_wf, text="KEY", variable=self.selected_scopeWf, value="3")
    self.scope3Wf.grid(row=1, column=0, padx=(10, 5), pady=(5, 10))

    self.scope_emptywf = ctk.CTkLabel(self.scopes_frame_wf, text="")
    self.scope_emptywf.grid(row=1, column=1, padx=(5, 10), pady=(5, 10))

    self.channels_frame_wf = ctk.CTkFrame(self.optionsWf)
    self.channels_frame_wf.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    self.ch1Wf = ctk.CTkRadioButton(self.channels_frame_wf, text="Ch1", variable=self.selected_channelWf, value="1")
    self.ch1Wf.grid(row=0, column=0, padx=(10, 5), pady=(10, 5))

    self.ch2Wf = ctk.CTkRadioButton(self.channels_frame_wf, text="Ch2", variable=self.selected_channelWf, value="2")
    self.ch2Wf.grid(row=0, column=1, padx=(5, 10), pady=(10, 5))

    self.ch3Wf = ctk.CTkRadioButton(self.channels_frame_wf, text="Ch3", variable=self.selected_channelWf, value="3")
    self.ch3Wf.grid(row=1, column=0, padx=(10, 5), pady=(5, 10))

    self.ch4Wf = ctk.CTkRadioButton(self.channels_frame_wf, text="Ch4", variable=self.selected_channelWf, value="4")
    self.ch4Wf.grid(row=1, column=1, padx=(5, 10), pady=(5, 10))

    self.start_buttonWf = ctk.CTkButton(self.optionsWf, text="Start", command=self.start_wf)
    self.start_buttonWf.grid(row=10, column=0, padx=20, pady=(20,50), columnspan=2, sticky="s")

    self.plot_wf = ctk.CTkFrame(self.tabview.tab("Waveform"))
    self.plot_wf.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    self.plot_wf.grid_rowconfigure(0, weight=1)
    self.plot_wf.grid_columnconfigure(0, weight=1)

    self.analysisWf = ctk.CTkFrame(self.tabviewWf.tab("Analysis"))
    self.analysisWf.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    self.analysisWf.grid_columnconfigure(0, weight=1)
    self.analysisWf.grid_columnconfigure(1, weight=1)

    self.dcr_button = ctk.CTkButton(self.analysisWf, text="Calculate Dcr", command=lambda: _do_dcr(self), width=120)
    self.dcr_button.grid(row=0, column=0, padx=(10), pady=(20,5), columnspan=2)
    self.dcr_output = ctk.CTkTextbox(self.analysisWf, width=90, height=30, activate_scrollbars=False)
    self.dcr_output.grid(row=1, column=0, padx=(10), pady=(5,10), columnspan=2)

    self.slider_wf = ctk.CTkSlider(self.analysisWf, from_=0, to=1,
                                    command=lambda value: _slider_event(self, value),
                                    number_of_steps=1)
    self.slider_wf.grid(row=2, column=0, padx=(10), pady=(5,10), columnspan=2)

    self.decrease_button = ctk.CTkButton(self.analysisWf, text="-", width=5,
                                         command=lambda: _decrease_slider_value(self))
    self.decrease_button.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    self.increase_button = ctk.CTkButton(self.analysisWf, text="+", width=5,
                                         command=lambda: _increase_slider_value(self))
    self.increase_button.grid(row=3, column=1, padx=10, pady=10, sticky="nsew")
