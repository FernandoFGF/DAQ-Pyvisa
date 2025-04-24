"""
Módulo que contiene la interfaz gráfica para las curvas IV.
"""
import customtkinter as ctk
import daq_gui_func as func

def setting_iv(self):
    """
    Módulo que contiene la interfaz gráfica para las curvas IV.

    Este módulo define una clase que representa la interfaz gráfica para la
    adquisición y análisis de curvas IV. Proporciona configuraciones y controles
    para establecer los parámetros de medición, iniciar la adquisición y mostrar
    los resultados en gráficos y salidas de texto.

    """

    # create tabview
    self.tabviewIV = ctk.CTkTabview(self.tabview.tab("IV Curves"), width=100)
    self.tabviewIV.grid(row=0, column=0, padx=(5, 5), pady=(5, 5), sticky="nsew")
    self.tabviewIV.add("DAQ")
    self.tabviewIV.add("Analysis")
    self.tabviewIV.tab("DAQ").grid_columnconfigure(0, weight=0)
    self.tabviewIV.tab("DAQ").grid_columnconfigure(1, weight=3)
    self.tabviewIV.tab("DAQ").grid_rowconfigure(0, weight=1)  # 100% de altura
    self.tabviewIV.tab("Analysis").grid_columnconfigure(0, weight=0)
    self.tabviewIV.tab("Analysis").grid_columnconfigure(1, weight=3)
    self.tabviewIV.tab("Analysis").grid_rowconfigure(0, weight=1)  # 100% de altura

    # IV Curves tab settings DAQ
    # Crear el primer contenedor (izquierda)
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

    # Crear el botón de start
    self.start_button = ctk.CTkButton(self.optionsIV, text="Start", command=self.start_iv)
    self.start_button.grid(row=7, column=0, padx=20, pady=(10,20), columnspan=2, sticky="s")

    # Crear el segundo contenedor (derecha)
    self.plotIV = ctk.CTkFrame(self.tabview.tab("IV Curves"))
    self.plotIV.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    self.plotIV.grid_rowconfigure(0, weight=1)
    self.plotIV.grid_columnconfigure(0, weight=1)

    #IV Curve setting analisys
    # Crear el primer contenedor (izquierda)
    self.analysisIV = ctk.CTkFrame(self.tabviewIV.tab("Analysis"))
    self.analysisIV.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    # Crear el botón de start Vbr
    self.vbr_button = ctk.CTkButton(self.analysisIV, text="Calculate Vbr", command=lambda: func.start_vbr(self, self.vbr_Output), width=120)
    self.vbr_button.grid(row=0, column=0, padx=(10), pady=(20,5))
    # Crear el widget Text para mostrar la salida
    self.vbr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.vbr_Output.grid(row=1, column=0, padx=(10), pady=(5,10))

    # Crear el botón de start Qr
    self.qr_button = ctk.CTkButton(self.analysisIV, text="Calculate Qr", command=lambda: func.start_qr(self, self.qr_Output), width=120)
    self.qr_button.grid(row=2, column=0, padx=(10), pady=(10,5))
    # Crear el widget Text para mostrar la salida
    self.qr_Output = ctk.CTkTextbox(self.analysisIV, width=90, height=30, activate_scrollbars=False)
    self.qr_Output.grid(row=3, column=0, padx=(10), pady=(5,5))

    # Crear el botón de start Complete
    self.complete_button = ctk.CTkButton(self.analysisIV, text="Draw complete", command=lambda: func.complete(self), width=120)
    self.complete_button.grid(row=4, column=0, padx=(10), pady=(20,5))
    