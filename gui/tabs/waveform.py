"""
Module for the SiPMs UGR waveform functionality.

DAQ Start is wired in ``daq_gui_main.py`` to
``DAQGUIFunctions.start_waveform_full``. The Analysis tab (DCR + slider
+ - buttons) delegates to ``analysis.waveform_analysis``.

Scope selection is no longer a manual radio button group. The
Waveform tab reads the currently-connected oscilloscope from
``self.connect_cards`` via :func:`App.get_active_scope` and shows a
read-only label with its name. The acquisition adapter (in
``acquisition/waveform_acquisition.py``) picks the SCPI dialect
from the legacy scope id (``1``/``2``/``3``); we pass both that
id and the real instrument id through
``DAQGUIFunctions.start_waveform_full``.
"""
import customtkinter as ctk
import os

from gui.instructions import build_instructions_icon as _build_instructions_icon


def _load_and_plot_waveform(self, file_index: int):
    path = str(self.path_wf.get())
    name = self.save_entry.get()
    if not path or not name:
        return
    file_path = os.path.join(path, f"{name}_{int(round(file_index))}.txt")
    if not os.path.exists(file_path):
        # Silent no-op: the user may have asked for an index past
        # the last written segment (e.g. after a cooperative stop
        # or a repeat-TSR early exit on Keysight). Do not print
        # an error so the slider feel is not noisy.
        return
    # Guard: ``self.ax`` / ``self.canvas`` are created by
    # ``plot_example_wf`` at app startup. If the slider is
    # touched before that (or the plot was never initialised),
    # fall back to a fresh figure inside ``self.plot_wf``.
    if not hasattr(self, "ax") or not hasattr(self, "canvas") or self.ax is None:
        if hasattr(self, "plot_wf"):
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            fig = Figure(figsize=(6, 4), dpi=100)
            self.ax = fig.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
            self.canvas.get_tk_widget().grid(
                row=0, column=0, padx=20, pady=20, sticky="nsew"
            )
        else:
            return
    data = self.gui_funcs.load_waveform_file(file_path)
    if data.size == 0:
        return
    num_points = int(self.num_points.get()) if self.num_points.get() else len(data)
    self.gui_funcs.plot_waveform(self.ax, data, num_points=num_points)
    # Force a repaint so the slider visibly moves the plot. The
    # analysis helper only mutates the axes; the canvas needs to
    # be told to redraw and Tk has to process the redraw event.
    try:
        self.canvas.draw()
        self.canvas.flush_events()
        self.update_idletasks()
    except Exception:
        pass


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
    # ``count`` is the number of segment files actually on disk.
    # The slider's last valid index is ``count - 1`` (we count
    # from 0), so the upper bound for stepping is ``count - 2``:
    # pressing + at index N moves to N+1 which must still be
    # strictly less than ``count - 1``.
    if count <= 1:
        return
    if current < count - 1:
        new = current + 1
        self.slider_wf.set(new)
        _load_and_plot_waveform(self, new)


def _refresh_scope_label(self) -> None:
    """Update the read-only 'Scope' label from connect_cards."""
    info = self.get_active_scope()
    if info is None:
        self.scopeWf_label.configure(
            text="(no scope connected)", text_color="#a0a0a0"
        )
        self.start_buttonWf.configure(state="disabled")
    else:
        _dialect, _iid, name = info
        self.scopeWf_label.configure(
            text=f"● {name}", text_color="#2ea043"
        )
        self.start_buttonWf.configure(state="normal")


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

    # Scope: a single read-only label that mirrors the connected
    # oscilloscope. No more RTA/RTO/KEY radio buttons.
    self.scopeWf_label_title = ctk.CTkLabel(self.optionsWf, text="Scope:", anchor="w")
    self.scopeWf_label_title.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="w")
    self.scopeWf_label = ctk.CTkLabel(
        self.optionsWf, text="(no scope connected)", anchor="w",
        text_color="#a0a0a0",
    )
    self.scopeWf_label.grid(row=2, column=1, padx=10, pady=(10, 0), sticky="w")

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

    self.start_buttonWf = ctk.CTkButton(self.optionsWf, text="Start", command=self.start_wf, state="disabled")
    self.start_buttonWf.grid(row=10, column=0, padx=20, pady=(20,5), columnspan=2, sticky="s")

    self.stop_buttonWf = ctk.CTkButton(self.optionsWf, text="Stop",
                                       command=self.stop_wf, state="disabled")
    self.stop_buttonWf.grid(row=11, column=0, padx=20, pady=(5,5),
                            columnspan=2, sticky="s")

    # Botón circular de "i" con las instrucciones del scope actual.
    self.instructionsWf_button = _build_instructions_icon(
        self.optionsWf, "Waveform",
    )
    self.instructionsWf_button.grid(row=12, column=1, padx=(0, 8), pady=(5, 50), sticky="se")

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

    _refresh_scope_label(self)
