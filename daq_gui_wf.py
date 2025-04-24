"""
Module for the SiPMs UGR DAQ waveform functionality.
"""
import customtkinter as ctk
import daq_gui_func as func

def setting_wf(self):
    """
    Configure the settings for the Waveform tab in the SiPMs UGR DAQ application.
    """
    # create tabview
    self.tabviewWf = ctk.CTkTabview(self.tabview.tab("Waveform"), width=100)
    self.tabviewWf.grid(row=0, column=0, padx=(5, 5), pady=(5, 5), sticky="nsew")
    self.tabviewWf.add("DAQ")
    self.tabviewWf.add("Analysis")
    self.tabviewWf.tab("DAQ").grid_columnconfigure(0, weight=0)
    self.tabviewWf.tab("DAQ").grid_columnconfigure(1, weight=3)
    self.tabviewWf.tab("DAQ").grid_rowconfigure(0, weight=1)  # 100% de altura
    self.tabviewWf.tab("Analysis").grid_columnconfigure(0, weight=0)
    self.tabviewWf.tab("Analysis").grid_columnconfigure(1, weight=3)
    self.tabviewWf.tab("Analysis").grid_rowconfigure(0, weight=1)  # 100% de altura

    # Waveform tab settings
    # Crear el primer contenedor (izquierda)
    self.optionsWf = ctk.CTkFrame(self.tabviewWf.tab("DAQ"))
    self.optionsWf.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    self.optionsWf.grid_rowconfigure(4, weight=1)
    self.optionsWf.columnconfigure(0, weight=1)
    self.optionsWf.columnconfigure(1, weight=1)

    self.timeWfLabel = ctk.CTkLabel(self.optionsWf, text="Set time to acquire:", anchor="w")
    self.timeWfLabel.grid(row=0, column=0, padx=10, pady=(20, 0), columnspan=2)
    self.timeWf = ctk.CTkEntry(self.optionsWf, placeholder_text="Default inmediatly")
    self.timeWf.grid(row=1, column=0, padx=10, pady=(0,0), columnspan=2)

    # Variable de control
    self.selected_channelWf = ctk.StringVar(value="1")  # Establecer el valor predeterminado
    self.selected_scopeWf = ctk.StringVar(value="1") #Elegir osciloscopio

    # Contenedor para Scopes
    self.scopes_frame_wf = ctk.CTkFrame(self.optionsWf)
    self.scopes_frame_wf.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    self.scope1Wf = ctk.CTkRadioButton(self.scopes_frame_wf, text="RTA", variable=self.selected_scopeWf, value="1")
    self.scope1Wf.grid(row=0, column=0, padx=(10, 5), pady=(10, 5))

    self.scope2Wf = ctk.CTkRadioButton(self.scopes_frame_wf, text="RTO", variable=self.selected_scopeWf, value="2")
    self.scope2Wf.grid(row=0, column=1, padx=(5, 10), pady=(10, 5))

    self.scope3Wf = ctk.CTkRadioButton(self.scopes_frame_wf, text="KEY", variable=self.selected_scopeWf, value="3")
    self.scope3Wf.grid(row=1, column=0, padx=(10, 5), pady=(5, 10))

    self.scope_emptywf = ctk.CTkLabel(self.scopes_frame_wf, text="")  # Espacio vacío
    self.scope_emptywf.grid(row=1, column=1, padx=(5, 10), pady=(5, 10))

    # Contenedor para Channels
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


    # Crear el botón de start
    self.start_buttonWf = ctk.CTkButton(self.optionsWf, text="Start", command=self.start_wf)
    self.start_buttonWf.grid(row=10, column=0, padx=20, pady=(20,50), columnspan=2, sticky="s")

    # Crear el segundo contenedor (derecha)
    self.plot_wf = ctk.CTkFrame(self.tabview.tab("Waveform"))
    self.plot_wf.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    self.plot_wf.grid_rowconfigure(0, weight=1)
    self.plot_wf.grid_columnconfigure(0, weight=1)

    #Spectrum setting analisys
    # Crear el primer contenedor (izquierda)
    self.analysisWf = ctk.CTkFrame(self.tabviewWf.tab("Analysis"))
    self.analysisWf.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    # Configurar el comportamiento de expansión
    self.analysisWf.grid_columnconfigure(0, weight=1)
    self.analysisWf.grid_columnconfigure(1, weight=1)

    # Crear el botón de start dcr
    self.dcr_button = ctk.CTkButton(self.analysisWf, text="Calculate Dcr", command=lambda: func.start_dcr(self, self.dcr_output), width=120)
    self.dcr_button.grid(row=0, column=0, padx=(10), pady=(20,5), columnspan=2)
    # Crear el widget Text para mostrar la salida
    self.dcr_output = ctk.CTkTextbox(self.analysisWf, width=90, height=30, activate_scrollbars=False)
    self.dcr_output.grid(row=1, column=0, padx=(10), pady=(5,10), columnspan=2)

    self.slider_wf = ctk.CTkSlider(self.analysisWf, from_=0, to=1, command=lambda value: func.slider_event(self, value), number_of_steps=1)
    self.slider_wf.grid(row=2, column=0, padx=(10), pady=(5,10), columnspan=2)

    self.decrease_button = ctk.CTkButton(self.analysisWf, text="-", width=5, command=lambda: func.decrease_slider_value(self))
    self.decrease_button.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

    self.increase_button = ctk.CTkButton(self.analysisWf, text="+", width=5, command=lambda: func.increase_slider_value(self))
    self.increase_button.grid(row=3, column=1, padx=10, pady=10, sticky="nsew")
