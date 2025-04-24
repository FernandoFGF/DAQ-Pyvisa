import logging

logging.basicConfig(filename='error.log', level=logging.ERROR)

try:
    """
    DAQ GUI Main Module

    This module contains the main code for the DAQ GUI application.

    Author: Fernando Fuentes-Guerra
    Date: 02/06/2023

    """
    import sys
    import customtkinter
    import daq_gui_func as func
    import daq_gui_iv as iv
    import daq_gui_spec as spec
    import daq_gui_wf as wf
    import lab_module as lm
    import threading

    #Selector apariencia
    customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
    customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

    class StdoutRedirector(object):
        """
        A class for redirecting standard output to a text widget.

        Args:
            text_widget (tk.Text): The text widget where the output will be redirected.

        Attributes:
            text_space (tk.Text): The text widget where the output will be redirected.

        Methods:
            write(string): Writes the given string to the text widget.
            flush(): Does nothing.

        """
        def __init__(self, text_widget):
            """
            Initialize the StdoutRedirector.

            Args:
                text_widget: The text widget where the redirected output will be displayed.
            """
            self.text_space = text_widget

        def write(self, string):
            """
            Write the string to the text widget.

            Args:
                string: The string to be written.
            """
            self.text_space.insert('end', string)
            self.text_space.see('end')

        def flush(self):
            """
            Flush the output.
            This method does nothing in this implementation.
            """
            pass

    class StderrRedirector(object):
        """
        A class for redirecting stderr output to a text widget.
        """
        def __init__(self, text_widget):
            """
            Initialize the StderrRedirector.

            Args:
                text_widget: The text widget where the redirected error output will be displayed.
            """
            self.text_space = text_widget

        def write(self, string):
            """
            Write the error string to the text widget.

            Args:
                string: The error string to be written.
            """
            self.text_space.insert('end', string, 'error')
            self.text_space.see('end')

        def flush(self):
            """
            Flush the error output.
            This method does nothing in this implementation.
            """
            pass


    class App(customtkinter.CTk):
        """
        Main application class for SiPMs UGR DAQ.
        """

        def __init__(self):
            """
            Initialize the App class.
            """
            super().__init__()

            # Variable initializations
            self.v_values_aux = customtkinter.StringVar()
            self.i_values_aux = customtkinter.StringVar()
            self.values_aux = customtkinter.StringVar()
            self.hist_data = customtkinter.StringVar()
            self.path_wf = customtkinter.StringVar()
            self.num_points = customtkinter.StringVar()

            # Title and geometry
            self.title("SiPMs UGR DAQ")
            self.geometry(f"{1200}x{700}")

            # Configure grid layout (4x4)
            self.grid_columnconfigure(0, weight=2)
            self.grid_columnconfigure(1, weight=0)
            self.grid_rowconfigure(0, weight=2)
            self.grid_rowconfigure((1, 2, 3), weight=0)

            # Tabview
            self.tabview = customtkinter.CTkTabview(self, width=250)
            self.tabview.grid(row=0, column=0, padx=(20, 20), pady=(10, 10), sticky="nsew")
            self.tabview.add("IV Curves")
            self.tabview.add("Spectrum")
            self.tabview.add("Waveform")
            self.tabview.tab("IV Curves").grid_columnconfigure(0, weight=0)
            self.tabview.tab("IV Curves").grid_columnconfigure(1, weight=3)
            self.tabview.tab("IV Curves").grid_rowconfigure(0, weight=1)  # 100% de altura
            self.tabview.tab("Spectrum").grid_columnconfigure(0, weight=0)
            self.tabview.tab("Spectrum").grid_columnconfigure(1, weight=3)
            self.tabview.tab("Spectrum").grid_rowconfigure(0, weight=1)  # 100% de altura
            self.tabview.tab("Waveform").grid_columnconfigure(0, weight=0)
            self.tabview.tab("Waveform").grid_columnconfigure(1, weight=3)
            self.tabview.tab("Waveform").grid_rowconfigure(0, weight=1)  # 100% de altura

            # create option frame
            self.option_frame = customtkinter.CTkFrame(self, width=140)
            self.option_frame.grid(row=0, column=1, padx=(0, 20), pady=(30, 20), rowspan=4, sticky="nsew")
            self.option_frame.grid_rowconfigure(4, weight=1)

            # Uppers options from option frame
            self.save_entry = customtkinter.CTkEntry(self.option_frame, placeholder_text="File name..")
            self.save_entry.grid(row=0, column=0, padx=10, pady=(20,10))
            self.save_button = customtkinter.CTkButton(self.option_frame)
            self.save_button.grid(row=1, column=0, padx=10, pady=(10,10))
            self.print_button = customtkinter.CTkButton(self.option_frame)
            self.print_button.grid(row=2, column=0, padx=10, pady=10)
            self.folder_button = customtkinter.CTkButton(self.option_frame)
            self.folder_button.grid(row=3, column=0, padx=10, pady=(10,20))

            # Down options from option frame
            self.appearance_mode_label = customtkinter.CTkLabel(self.option_frame, text="Appearance Mode:", anchor="w")
            self.appearance_mode_label.grid(row=5, column=0, padx=10, pady=(0, 0))
            self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.option_frame, values=["Light", "Dark", "System"], command=self.change_appearance)
            self.appearance_mode_optionemenu.grid(row=6, column=0, padx=10, pady=(0, 5))
            self.scaling_label = customtkinter.CTkLabel(self.option_frame, text="UI Scaling:", anchor="w")
            self.scaling_label.grid(row=7, column=0, padx=10, pady=(5, 0))
            self.scaling_optionemenu = customtkinter.CTkOptionMenu(self.option_frame, values=["80%", "90%", "100%", "110%", "120%"], command=self.change_scaling_event)
            self.scaling_optionemenu.grid(row=8, column=0, padx=10, pady=(0, 100))

            # create textbox
            self.textbox = customtkinter.CTkTextbox(self, width=250)
            self.textbox.grid(row=1, column=0, padx=(20, 20), pady=(10, 20), sticky="nsew")

            spec.setting_spec(self)

            func.plot_example_spec(self)

            wf.setting_wf(self)

            func.plot_example_wf(self)

            iv.setting_iv(self)

            func.plot_example_iv(self)

            # set default values
            self.save_button.configure(text="Save results", command=self.save_results)
            self.print_button.configure(text="Print results", command=self.save_plot_as_png)
            self.folder_button.configure(text="Open folder", command=self.open_results)
            self.appearance_mode_optionemenu.set("System")
            self.scaling_optionemenu.set("100%")
            self.options.set("SMU")
            sys.stdout = StdoutRedirector(self.textbox)
            sys.stderr = StderrRedirector(self.textbox)

        def change_appearance(self, new_appearance_mode: str):
            """
            Event handler for changing the appearance mode.

            Args:
                new_appearance_mode (str): The new appearance mode selected.
            """
            customtkinter.set_appearance_mode(new_appearance_mode)

        def change_scaling_event(self, new_scaling: str):
            """
            Event handler for changing the UI scaling.

            Args:
                new_scaling (str): The new scaling value selected.
            """
            new_scaling_float = int(new_scaling.replace("%", "")) / 100
            customtkinter.set_widget_scaling(new_scaling_float)

        def start_iv(self):
            """
            Start the IV curve measurement.
            """
            try:
                func.start_iv(self)
                print("IV curve finished")
                v_values=self.v_values_aux.get()
                i_values=self.i_values_aux.get()
                # Dividir la cadena en elementos individuales
                v_values = v_values.split(', ')
                i_values = i_values.split(', ')
                # Convertir los elementos en floats y crear la lista resultante
                #print(i_values)
                v_values = [float(x) for x in v_values]
                i_values = [float(x) for x in i_values]
                #print(v_values)
                # Obtener la figura y el lienzo
                fig = self.canvas.figure

                # Dibujar el punto rojo en el lienzo
                self.canvas.draw()
                a_x = fig.gca()
                a_x.cla()
                # Agregar etiquetas de ejes
                a_x.set_xlabel('Voltios')
                a_x.set_ylabel('Amperios')
                a_x.plot(v_values, i_values)

                # Actualizar la figura
                fig.canvas.draw()

            except Exception as e_error:
                print("Error:", e_error)
            finally:
                # Habilitar el botón Start nuevamente al finalizar
                lm.beep()
                self.start_button.configure(state="normal")

        def save_results(self):
            """
            Save the measurement results.
            """
            func.save_results(self)

        def open_results(self):
            """
            Open the folder containing the results.
            """
            func.open_results(self)

        def save_plot_as_png(self):
            """
            Save the plot as a PNG image.
            """
            func.save_plot_as_png(self)

        def start_spectrum(self):
            """
            Start the spectrum measurement.
            """
            func.thread_spectrum(self)

        def stop_spectrum(self):

            #self.thread_spec_activo = False
            # Esperar a que el hilo termine su ejecución
            #self.thread_spec.join()
            #self.stopSpec_button.configure(state="disable")
            #self.startSpec_button.configure(state="normal")
            print("No para")

        def start_wf(self):
            """
            Start the waveform measurement.
            """
            func.thread_wf(self)


    app = App()
    app.mainloop()

except Exception as e:
    logging.error(str(e))

