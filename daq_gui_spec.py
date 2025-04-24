"""
Module for the SiPMs UGR DAQ spectrum functionality.
"""
import customtkinter as ctk
import daq_gui_func as func

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
    self.selected_scopeSpec = ctk.StringVar(value="1") #Elegir osciloscopio

    # Contenedor para Scopes
    self.scopes_frameSpec = ctk.CTkFrame(self.optionSpectrum)
    self.scopes_frameSpec.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    self.scope1Spec = ctk.CTkRadioButton(self.scopes_frameSpec, text="RTA", variable=self.selected_scopeSpec, value="1")
    self.scope1Spec.grid(row=0, column=0, padx=(10, 5), pady=(10, 5))

    self.scope2Spec = ctk.CTkRadioButton(self.scopes_frameSpec, text="RTO", variable=self.selected_scopeSpec, value="2")
    self.scope2Spec.grid(row=0, column=1, padx=(5, 10), pady=(10, 5))

    self.scope3Spec = ctk.CTkRadioButton(self.scopes_frameSpec, text="KEY", variable=self.selected_scopeSpec, value="3")
    self.scope3Spec.grid(row=1, column=0, padx=(10, 5), pady=(5, 10))

    self.scope_emptySpec = ctk.CTkLabel(self.scopes_frameSpec, text="")  # Espacio vacío
    self.scope_emptySpec.grid(row=1, column=1, padx=(5, 10), pady=(5, 10))

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
    self.startSpec_button = ctk.CTkButton(self.optionSpectrum, text="Start", command=self.start_spectrum)
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
    self.peaks_button = ctk.CTkButton(self.analysisSpec, text="Finder peaks",command=lambda: func.finding_peaks(self),width=120)
    self.peaks_button.grid(row=0, column=0, padx=(10), pady=(20,5))
