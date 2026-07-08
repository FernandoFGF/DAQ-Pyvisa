"""
Module for the SiPMs UGR spectrum functionality.

The "Finder peaks" button delegates to ``analysis.spectrum_analysis``.
The DAQ Start button is wired in ``daq_gui_main.py`` to
``DAQGUIFunctions.start_spectrum_full``.

Scope selection is no longer a manual radio button group. The
Spectrum tab reads the currently-connected oscilloscope from
``self.connect_cards`` via :func:`App.get_active_scope` and shows a
read-only label with its name. The acquisition adapter (in
``acquisition/spectrum_acquisition.py``) knows the SCPI dialect
from the legacy scope id (``1``/``2``/``3``); we pass both that
id and the real instrument id through
``DAQGUIFunctions.start_spectrum_full``.
"""
import customtkinter as ctk


def _do_finding_peaks(self):
    from analysis.spectrum_analysis import parse_hist_data
    raw = self.hist_data.get()
    data = parse_hist_data(raw)
    if data.size == 0:
        print("Primero debes de recoger datos que analizar.")
        return
    self.gui_funcs.plot_histogram_with_peaks(self.ax, data)


def _refresh_scope_label(self) -> None:
    """Update the read-only 'Scope' label from connect_cards."""
    info = self.get_active_scope()
    if info is None:
        self.scopeSpec_label.configure(
            text="(no scope connected)", text_color="#a0a0a0"
        )
        self.startSpec_button.configure(state="disabled")
    else:
        _dialect, _iid, name = info
        self.scopeSpec_label.configure(
            text=f"● {name}", text_color="#2ea043"
        )
        self.startSpec_button.configure(state="normal")


def setting_spec(self):
    """
    Configure the settings for the Spectrum tab in the SiPMs UGR DAQ application.
    """
    # create tabview
    self.tabviewSpec = ctk.CTkTabview(self.tabview.tab("Spectrum"), width=50)
    self.tabviewSpec.grid(row=0, column=0, padx=(5, 5), pady=(5, 5), sticky="nsew")
    self.tabviewSpec.add("DAQ")
    self.tabviewSpec.add("Analysis")
    self.tabviewSpec.tab("DAQ").grid_columnconfigure(0, weight=0)
    self.tabviewSpec.tab("DAQ").grid_columnconfigure(1, weight=3)
    self.tabviewSpec.tab("DAQ").grid_rowconfigure(0, weight=1)  # 100% de altura
    self.tabviewSpec.tab("Analysis").grid_columnconfigure(0, weight=0)
    self.tabviewSpec.tab("Analysis").grid_columnconfigure(1, weight=3)
    self.tabviewSpec.tab("Analysis").grid_rowconfigure(0, weight=1)  # 100% de altura

    # Spectrum tab settings
    # Crear el primer contenedor (izquierda)
    self.optionSpectrum = ctk.CTkFrame(self.tabviewSpec.tab("DAQ"))
    self.optionSpectrum.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    self.optionSpectrum.grid_rowconfigure(4, weight=1)
    self.optionSpectrum.columnconfigure(0, weight=1)
    self.optionSpectrum.columnconfigure(1, weight=1)

    self.spec_entries = ctk.CTkLabel(self.optionSpectrum, text="Set entries:", anchor="w")
    self.spec_entries.grid(row=0, column=0, padx=10, pady=(20, 0), columnspan=2)
    self.entries = ctk.CTkEntry(self.optionSpectrum, placeholder_text="Set entries to hist")
    self.entries.grid(row=1, column=0, padx=10, pady=(0,0), columnspan=2)

    self.selected_channelSpec = ctk.StringVar(value="MA1")  # Establecer el valor predeterminado

    # Scope: a single read-only label that mirrors the connected
    # oscilloscope in self.connect_cards. No more RTA/RTO/KEY
    # radio buttons: the SCPI dialect is now derived from the
    # instrument_id in the adapter layer.
    self.scopeSpec_label_title = ctk.CTkLabel(self.optionSpectrum, text="Scope:", anchor="w")
    self.scopeSpec_label_title.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="w")
    self.scopeSpec_label = ctk.CTkLabel(
        self.optionSpectrum, text="(no scope connected)", anchor="w",
        text_color="#a0a0a0",
    )
    self.scopeSpec_label.grid(row=2, column=1, padx=10, pady=(10, 0), sticky="w")

    # Contenedor para Channels
    self.channels_frameSpec = ctk.CTkFrame(self.optionSpectrum)
    self.channels_frameSpec.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    self.ch1Spec = ctk.CTkRadioButton(self.channels_frameSpec, text="Ch1", variable=self.selected_channelSpec, value="MA1")
    self.ch1Spec.grid(row=0, column=0, padx=(10, 5), pady=(10, 5))

    self.ch2Spec = ctk.CTkRadioButton(self.channels_frameSpec, text="Ch2", variable=self.selected_channelSpec, value="MA2")
    self.ch2Spec.grid(row=0, column=1, padx=(5, 10), pady=(10, 5))

    self.ch3Spec = ctk.CTkRadioButton(self.channels_frameSpec, text="Ch3", variable=self.selected_channelSpec, value="MA3")
    self.ch3Spec.grid(row=1, column=0, padx=(10, 5), pady=(5, 10))

    self.ch4Spec = ctk.CTkRadioButton(self.channels_frameSpec, text="Ch4", variable=self.selected_channelSpec, value="MA4")
    self.ch4Spec.grid(row=1, column=1, padx=(5, 10), pady=(5, 10))


    # Crear el botón de start
    self.startSpec_button = ctk.CTkButton(self.optionSpectrum, text="Start", command=self.start_spectrum, state="disabled")
    self.startSpec_button.grid(row=10, column=0, padx=10, pady=(20,5), columnspan=2, sticky="s")

    # Crear el botón de stop
    self.stopSpec_button = ctk.CTkButton(self.optionSpectrum, text="Stop", command=self.stop_spectrum, state="disable")
    self.stopSpec_button.grid(row=11, column=0, padx=10, pady=(5,50), columnspan=2, sticky="s")

    # Crear el segundo contenedor (derecha)
    self.liveplot = ctk.CTkFrame(self.tabview.tab("Spectrum"))
    self.liveplot.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    self.liveplot.grid_rowconfigure(0, weight=1)
    self.liveplot.grid_columnconfigure(0, weight=1)

    #Spectrum setting analisys
    # Crear el primer contenedor (izquierda)
    self.analysisSpec = ctk.CTkFrame(self.tabviewSpec.tab("Analysis"))
    self.analysisSpec.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    # Crear el botón de fitting
    self.peaks_button = ctk.CTkButton(self.analysisSpec, text="Finder peaks",command=lambda: _do_finding_peaks(self),width=120)
    self.peaks_button.grid(row=0, column=0, padx=(10), pady=(20,5))

    # Initial population of the scope label from current connect state.
    _refresh_scope_label(self)
