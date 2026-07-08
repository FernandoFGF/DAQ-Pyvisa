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
    import time
    import customtkinter
    from gui.facade import DAQGUIFunctions
    from gui.tabs import connect as connect_tab
    from gui.tabs import arbgen as arbgen_tab
    from gui.tabs import iv as iv
    from gui.tabs import spectrum as spec
    from gui.tabs import waveform as wf
    import lab_module as lm
    import os
    from config_loader import get_config
    from acquisition.save import ensure_dir
    from analysis.spectrum_analysis import plot_histogram_with_peaks

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

            If the underlying widget has been destroyed (the window is
            already closing), silently drop the write instead of raising
            a TclError during teardown.
            """
            try:
                self.text_space.insert('end', string)
                self.text_space.see('end')
            except Exception:
                pass

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
            Write the error string to the text widget. If the widget has
            been destroyed, silently drop the write.

            Args:
                string: The error string to be written.
            """
            try:
                self.text_space.insert('end', string, 'error')
                self.text_space.see('end')
            except Exception:
                pass

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
            
            # Initialize new architecture components
            self.gui_funcs = DAQGUIFunctions()
            self.config = get_config()
            
            # Add GUI callbacks for the new architecture
            self.gui_funcs.add_gui_callback('progress', self.update_progress)
            self.gui_funcs.add_gui_callback('data_ready', self.update_data)
            self.gui_funcs.add_gui_callback('error', self.show_error)

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
            self.tabview.add("Connect")
            self.tabview.add("IV Curves")
            self.tabview.add("Spectrum")
            self.tabview.add("Waveform")
            self.tabview.tab("IV Curves").grid_columnconfigure(0, weight=0)
            self.tabview.tab("IV Curves").grid_columnconfigure(1, weight=3)
            self.tabview.tab("IV Curves").grid_rowconfigure(0, weight=1)
            self.tabview.tab("Spectrum").grid_columnconfigure(0, weight=0)
            self.tabview.tab("Spectrum").grid_columnconfigure(1, weight=3)
            self.tabview.tab("Spectrum").grid_rowconfigure(0, weight=1)
            self.tabview.tab("Waveform").grid_columnconfigure(0, weight=0)
            self.tabview.tab("Waveform").grid_columnconfigure(1, weight=3)
            self.tabview.tab("Waveform").grid_rowconfigure(0, weight=1)
            self.tabview.tab("Connect").grid_columnconfigure(0, weight=1)
            self.tabview.tab("Connect").grid_rowconfigure(0, weight=1)

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

            # Instrument connection buttons — superseded by the Connect tab.
            # The four buttons (Connect All / Connect SMU / Connect Scope /
            # Disconnect All) used to live in the right option_frame; the
            # new Connect tab exposes per-instrument cards with the same
            # functionality. The methods on App (connect_instruments,
            # connect_specific_instrument, disconnect_instruments) and on
            # self.gui_funcs (connect_all_instruments, connect_specific_instrument,
            # disconnect_all_instruments) are kept in case future code wants
            # to wire them elsewhere.
            # self.connect_button = customtkinter.CTkButton(self.option_frame, text="Connect All Instruments", command=self.connect_instruments)
            # self.connect_button.grid(row=4, column=0, padx=10, pady=(10, 5))
            # self.connect_smu_button = customtkinter.CTkButton(self.option_frame, text="Connect SMU", command=lambda: self.connect_specific_instrument("smu"))
            # self.connect_smu_button.grid(row=5, column=0, padx=10, pady=(5, 2))
            # self.connect_scope_button = customtkinter.CTkButton(self.option_frame, text="Connect Scope", command=lambda: self.connect_specific_instrument("scope1"))
            # self.connect_scope_button.grid(row=6, column=0, padx=10, pady=(2, 5))
            # self.disconnect_button = customtkinter.CTkButton(self.option_frame, text="Disconnect All", command=self.disconnect_instruments)
            # self.disconnect_button.grid(row=7, column=0, padx=10, pady=(5, 10))

            # Down options from option frame
            self.appearance_mode_label = customtkinter.CTkLabel(self.option_frame, text="Appearance Mode:", anchor="w")
            self.appearance_mode_label.grid(row=8, column=0, padx=10, pady=(0, 0))
            self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.option_frame, values=["Light", "Dark", "System"], command=self.change_appearance)
            self.appearance_mode_optionemenu.grid(row=9, column=0, padx=10, pady=(0, 5))
            self.scaling_label = customtkinter.CTkLabel(self.option_frame, text="UI Scaling:", anchor="w")
            self.scaling_label.grid(row=10, column=0, padx=10, pady=(5, 0))
            self.scaling_optionemenu = customtkinter.CTkOptionMenu(self.option_frame, values=["80%", "90%", "100%", "110%", "120%"], command=self.change_scaling_event)
            self.scaling_optionemenu.grid(row=11, column=0, padx=10, pady=(0, 10))

            # Connected instruments (informational). Small, low-emphasis
            # list that mirrors self.connect_cards. Updated by
            # _refresh_connected_list() whenever a card connects or
            # disconnects in the Connect tab.
            self.connected_label = customtkinter.CTkLabel(
                self.option_frame, text="Connected:", anchor="w",
                text_color="#888",
            )
            self.connected_label.grid(row=12, column=0, padx=10, pady=(8, 2), sticky="w")

            self.connected_list = customtkinter.CTkTextbox(
                self.option_frame, width=140, height=120, activate_scrollbars=True,
            )
            self.connected_list.grid(row=13, column=0, padx=10, pady=(0, 16), sticky="ew")
            self.connected_list.configure(state="disabled")
            self._refresh_connected_list()

            # create textbox
            self.textbox = customtkinter.CTkTextbox(self, width=250)
            self.textbox.grid(row=1, column=0, padx=(20, 20), pady=(10, 20), sticky="nsew")

            connect_tab.setting_connect(self)

            arbgen_tab.setting_arbgen(self)

            spec.setting_spec(self)

            plot_example_spec(self)

            # Bind the scope-label refresher so Connect can call it
            # whenever a card connects / disconnects.
            self._refresh_scope_label_spec = (
                lambda: spec._refresh_scope_label(self)
            )

            wf.setting_wf(self)

            plot_example_wf(self)

            self._refresh_scope_label_wf = (
                lambda: wf._refresh_scope_label(self)
            )

            # Initial population from whatever was already connected
            # (none on a fresh boot, but be safe).
            self._refresh_scope_label_spec()
            self._refresh_scope_label_wf()

            iv.setting_iv(self)

            plot_example_iv(self)

            # set default values
            self.save_button.configure(text="Save results", command=self.save_results)
            self.print_button.configure(text="Print results", command=self.save_plot_as_png)
            self.folder_button.configure(text="Open folder", command=self.open_results)
            self.appearance_mode_optionemenu.set("System")
            self.scaling_optionemenu.set("100%")
            self.options.set("SMU")
            self._stdout_original = sys.stdout
            self._stderr_original = sys.stderr
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
        
        def update_progress(self, progress: float):
            """
            Update progress display.
            
            Args:
                progress: Progress percentage (0-100)
            """
            print(f"Progress: {progress:.1f}%")
        
        def update_data(self, data):
            """
            Update data display. The StdoutRedirector already shows
            a generic "Data ready!" line in the textbox whenever a
            payload arrives, so this handler focuses on the typed
            payload.
            """
            if isinstance(data, dict):
                if 'voltage_array' in data and 'current_array' in data:
                    # IV measurement data
                    self.v_values_aux.set(', '.join(map(str, data['voltage_array'])))
                    self.i_values_aux.set(', '.join(map(str, data['current_array'])))
                elif 'message' in data:
                    print(data['message'])

        def _refresh_connected_list(self) -> None:
            """Repaint the small 'Connected' panel in the right option frame.

            Reads ``self.connect_cards`` (populated by the Connect tab)
            and lists the model field of every instrument with a live
            connection (parsed from its *IDN? response). Falls back to
            the static name when no *IDN? has been captured yet.
            No-op if the panel hasn't been built yet.
            """
            widget = getattr(self, "connected_list", None)
            if widget is None:
                return
            names = []
            cards = getattr(self, "connect_cards", {}) or {}
            try:
                from gui.tabs.connect import DEFAULT_CARDS, parse_idn_model
                ordered_ids = [iid for iid, _, _ in DEFAULT_CARDS]
            except Exception:
                ordered_ids = list(cards.keys())
                parse_idn_model = lambda s: ""  # noqa: E731
            for iid in ordered_ids:
                card = cards.get(iid)
                if not card or card.get("connection") is None:
                    continue
                model = parse_idn_model(card.get("idn", ""))
                display = model if model else card.get("name", iid)
                names.append(f"● {display}")

            text = "\n".join(names) if names else "(none)"
            try:
                widget.configure(state="normal")
                widget.delete("1.0", "end")
                widget.insert("end", text)
                widget.configure(state="disabled")
            except Exception:
                pass

        def get_active_scope(self):
            """Return the connected oscilloscope in ``(dialect, instrument_id,
            friendly_name)`` form, or ``None`` if no scope is connected.

            ``dialect`` is the SCPI variant id used by the
            acquisition adapters (``"1"``=RTA, ``"2"``=RTO,
            ``"3"``=KEY). ``instrument_id`` is the id used to open
            the VISA session (``"scope1"``/``"scope2"``/``"scope3"``).
            ``friendly_name`` is the short name shown on the Connect
            card (RTA / RTO / KEY). Useful for the Spectrum and
            Waveform tabs which used to expose manual scope-selector
            radio buttons.
            """
            try:
                from gui.tabs.connect import card_info
            except Exception:
                return None
            cards = getattr(self, "connect_cards", {}) or {}
            for instrument_id, widgets in cards.items():
                if not isinstance(widgets, dict):
                    continue
                if widgets.get("connection") is None:
                    continue
                info = card_info(instrument_id)
                if info is None:
                    continue
                _, name, _desc, dialect = info
                if dialect is None:
                    continue
                return (dialect, instrument_id, name)
            return None

        def show_error(self, error_message: str):
            """
            Show error message.
            
            Args:
                error_message: Error message to display
            """
            print(f"Error: {error_message}")
        
        def connect_instruments(self):
            """
            Connect to all configured instruments.
            """
            try:
                self.gui_funcs.connect_all_instruments()
                print("All instruments connected successfully")
            except Exception as e:
                print(f"Failed to connect instruments: {e}")
        
        def connect_specific_instrument(self, instrument_id: str):
            """
            Connect to a specific instrument.
            
            Args:
                instrument_id: ID of the instrument to connect
            """
            try:
                success = self.gui_funcs.connect_specific_instrument(instrument_id)
                if success:
                    print(f"Successfully connected to {instrument_id}")
                else:
                    print(f"Failed to connect to {instrument_id}")
            except Exception as e:
                print(f"Error connecting to {instrument_id}: {e}")
        
        def disconnect_instruments(self):
            """
            Disconnect from all instruments.
            """
            try:
                self.gui_funcs.disconnect_all_instruments()
                print("All instruments disconnected")
            except Exception as e:
                print(f"Failed to disconnect instruments: {e}")

        def start_iv(self):
            """
            Start the IV curve measurement using the new architecture.
            """
            try:
                v_start = float(self.vStart.get()) if self.vStart.get() else 1.0
                v_stop = float(self.vStop.get()) if self.vStop.get() else -40.0
                v_step = float(self.vStep.get()) if self.vStep.get() else 0.05
                option = self.options.get()
            except ValueError:
                print("Error: Los valores ingresados deben ser números válidos.")
                self.start_button.configure(state="normal")
                return

            self.start_button.configure(state="disabled")

            def _on_results(payload):
                v = payload['voltage']
                i = payload['current']
                self.v_values_aux.set(', '.join(f"{x:.6g}" for x in v))
                self.i_values_aux.set(', '.join(f"{x:.6g}" for x in i))

                fig = self.canvas.figure
                self.canvas.draw()
                ax = fig.gca()
                ax.cla()
                ax.set_xlabel('Voltios')
                ax.set_ylabel('Amperios')
                ax.plot(v, i)
                fig.canvas.draw()
                print("IV curve finished")

            def _on_error(msg):
                print("Error:", msg)

            def _on_finish():
                lm.beep()
                self.start_button.configure(state="normal")

            def _on_complete():
                # Called from a worker thread; hop back to the Tk main loop
                # so widget state updates are safe.
                self.after(0, _on_finish)

            def _wrapped_results(payload):
                self.after(0, lambda p=payload: (_on_results(p), _on_complete()))

            self.gui_funcs.start_iv_full(
                v_start=v_start,
                v_stop=v_stop,
                v_step=v_step,
                option=option,
                results_callback=_wrapped_results,
                error_callback=lambda m: self.after(0, lambda: _on_error(m)),
            )

        def save_results(self):
            """
            Save the measurement results to the active tab's folder.
            """
            name = self.save_entry.get()
            path = str(lm.get_path(self.tabview.get())) + "/"
            if not name:
                print("Introduzca un nombre antes de guardar.")
                return
            ensure_dir(path)
            tab = self.tabview.get()
            if tab == "IV Curves":
                self.gui_funcs.save_iv_results_to(name, path)
                print(f"[Save] Fichero '{name}.txt' guardado correctamente en {path}.")
            elif tab == "Spectrum":
                self.gui_funcs.save_spectrum_results_to(name, path)
                print(f"[Save] Fichero '{name}.txt' guardado correctamente en {path}.")
            elif tab == "Waveform":
                print("Esta funcion se guarda automaticamente")

        def open_results(self):
            """
            Open the folder containing the results in the system file explorer.
            """
            path = str(lm.get_path(self.tabview.get()))
            try:
                path = path.replace("/", "\\")
                if not os.path.isdir(path):
                    raise Exception("La ruta especificada no existe o no es una carpeta.")
                os.system(f'explorer "{path}"')
            except Exception as e_error:
                print("Error al abrir la carpeta:", e_error)

        def save_plot_as_png(self):
            """
            Save the active matplotlib figure as a PNG image.
            """
            name = self.save_entry.get()
            if not name:
                print("Introduzca un nombre antes de guardar.")
                return
            path = str(lm.get_path(self.tabview.get())) + "/"
            ensure_dir(path)
            self.gui_funcs.save_plot_as_png(self.canvas.figure, name, path)

        def start_spectrum(self):
            """
            Start the spectrum measurement using the new architecture.
            """
            num_datos_raw = self.entries.get()
            if not num_datos_raw:
                print("Introduce un valor para entries primero.")
                return
            try:
                num_datos = int(num_datos_raw)
            except ValueError:
                print("El número de muestras debe ser un entero.")
                return
            if num_datos <= 0:
                print("El número de muestras debe ser > 0.")
                return
            active = self.get_active_scope()
            if active is None:
                print("Connect an oscilloscope in the Connect tab first.")
                return
            scope, instrument_id, friendly = active
            channel = self.selected_channelSpec.get()
            print(f"[Spectrum] Start: {num_datos} samples, scope={friendly} "
                  f"({instrument_id}, dialect {scope!r}), channel={channel}")

            # If the user did not provide a file name, fall back to a
            # default like "default-2026-07-08-10-55-12" so the
            # "Open folder" button always has something to look at and
            # the eventual save step never fails on a missing name.
            if not self.save_entry.get().strip():
                default_name = "default-" + time.strftime("%Y-%m-%d-%H-%M-%S")
                self.save_entry.delete(0, "end")
                self.save_entry.insert(0, default_name)
                print(f"[Spectrum] No file name set, using '{default_name}'.")

            # Make sure the Spectrum tab is the active one so the live
            # histogram is actually visible while it grows. Switching
            # tabs also realizes the embedded matplotlib canvas, which
            # is required for draw() to paint to the screen.
            try:
                self.tabview.set("Spectrum")
            except Exception:
                pass

            def _refresh_liveplot(arr, final: bool = False):
                """Redraw the live histogram with the latest sample batch.

                We rebuild the figure on every progress callback so the
                canvas is always realized inside the active Spectrum
                tab. Reusing a stale canvas created before the tab was
                ever shown would result in draw() calls that never
                reach the screen.

                The DAQ tab shows a plain histogram only; peak finding
                and the colour overlay are reserved for the Analysis
                tab's "Finder peaks" button.
                """
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                fig = Figure(figsize=(6, 4), dpi=100)
                self.ax = fig.add_subplot(111)
                self.ax.set_xlabel("Charge(Vs)")
                self.ax.hist(arr, bins=50)
                if hasattr(self, "canvas") and self.canvas is not None:
                    try:
                        self.canvas.get_tk_widget().destroy()
                    except Exception:
                        pass
                self.canvas = FigureCanvasTkAgg(fig, self.liveplot)
                self.canvas.get_tk_widget().grid(
                    row=0, column=0, padx=20, pady=20, sticky="nsew"
                )
                self.canvas.draw()
                self.canvas.flush_events()
                self.update_idletasks()

            def _on_results(payload):
                _refresh_liveplot(payload['data'], final=True)
                data = payload['data']
                self.values_aux.set(" ".join(f"{x:.6g}" for x in data))
                # Update hist_data for the Analysis tab (Finder peaks button).
                self.hist_data.set("(" + ", ".join(f"{x:.6g}" for x in data) + ")")
                print(f"[Spectrum] Finish histogram ({data.size} samples).")

            def _on_progress(arr):
                _refresh_liveplot(arr, final=False)

            def _on_error(msg):
                print("[Spectrum] Error:", msg)

            self._spectrum_user_stopped = False
            self.startSpec_button.configure(state="disabled")
            self.stopSpec_button.configure(state="normal")

            # Make sure today's Spectrum output folder exists so the
            # "Open folder" button works even if the user never saved
            # the file manually. We do not write a file here, just
            # create the directory.
            try:
                lm.create_directory(lm.get_path("Spectrum"))
            except Exception as _e_dir:
                print("[Spectrum] Could not create output folder:", _e_dir)

            def _reenable():
                lm.beep()
                if not self._spectrum_user_stopped:
                    self.startSpec_button.configure(state="normal")
                self.stopSpec_button.configure(state="disabled")

            self.gui_funcs.start_spectrum_full(
                num_datos=num_datos,
                scope=scope,
                channel=channel,
                instrument_id=instrument_id,
                results_callback=lambda p: self.after(0, lambda: (_on_results(p), _reenable())),
                progress_callback=lambda arr: self.after(0, lambda a=arr: _on_progress(a)),
                error_callback=lambda m: self.after(0, lambda: (_on_error(m), _reenable())),
            )

        def stop_spectrum(self):
            """Request a cooperative stop of the running spectrum worker.

            The adapter checks ``_stop_requested`` between samples, so
            the worker will finish its current iteration (or the
            in-flight query's timeout) and then exit. ``Start`` stays
            disabled until the worker has actually returned, so we
            don't risk starting a second acquisition on top of the
            first.
            """
            acq = self.gui_funcs.get_running_spectrum()
            if acq is None:
                print("[Spectrum] No hay medición en curso.")
                return
            self._spectrum_user_stopped = True
            print("[Spectrum] Solicitando parada tras la muestra actual...")
            acq.request_stop()

        def start_wf(self):
            """
            Start the waveform measurement using the new architecture.
            """
            time_seconds_raw = self.timeWf.get()
            time_seconds = float(time_seconds_raw) if time_seconds_raw else 0.0
            name = self.save_entry.get()
            if not name:
                print("Introduce un nombre al fichero")
                return
            active = self.get_active_scope()
            if active is None:
                print("Connect an oscilloscope in the Connect tab first.")
                return
            scope, instrument_id, _name = active
            channel = self.selected_channelWf.get()
            save_root = str(lm.get_path("Waveform"))

            def _on_results(payload):
                # Update GUI state with the captured waveform.
                self.path_wf.set(payload['path_d'])
                self.num_points.set(str(payload['num_points']))

                y_data = payload['y_data']
                x_data = payload['x_data']

                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                fig = Figure(figsize=(6, 4), dpi=100)
                self.ax = fig.add_subplot(111)
                self.ax.clear()
                self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
                self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
                self.ax.plot(x_data, y_data)
                self.ax.set_xlabel('Time(S)')
                self.ax.set_ylabel('Voltaje(V)')
                fig.canvas.draw()

                count, _ = self.gui_funcs.count_waveform_files(payload['path_d'], name)
                self.slider_wf.configure(to=max(count - 1, 0),
                                         number_of_steps=max(count - 1, 0))
                print("Finish waveform.")

            def _on_error(msg):
                print("Error:", msg)

            def _on_finish():
                lm.beep()

            self.gui_funcs.start_waveform_full(
                scope=scope,
                channel=channel,
                time_seconds=time_seconds,
                name=name,
                save_root=save_root,
                instrument_id=instrument_id,
                results_callback=lambda p: self.after(0, lambda: (_on_results(p), _on_finish())),
                error_callback=lambda m: self.after(0, lambda: (_on_error(m), _on_finish())),
            )
        
        def on_closing(self):
            """
            Handle application closing.

            Order matters:
              1. Restore real stdout/stderr so later output goes to
                 the console (and so the redirector doesn't try to
                 write into a destroyed textbox).
              2. Close every instrument connection opened in the
                 Connect tab. pyvisa's ``ResourceManager`` runs an
                 ``atexit`` hook that iterates over its open sessions
                 and tries to RPC-close them; if we leave VXI-11
                 sockets open they hang on a blocking ``select`` and
                 trigger the ``KeyboardInterrupt``-looking traceback
                 the user has been seeing at shutdown.
              3. Run the rest of the cleanup (stop measurements).
              4. Destroy the Tk widgets.
            """
            # Restore real streams first.
            try:
                if getattr(self, "_stdout_original", None) is not None:
                    sys.stdout = self._stdout_original
                if getattr(self, "_stderr_original", None) is not None:
                    sys.stderr = self._stderr_original
            except Exception:
                pass

            # Close every connection that the Connect tab opened.
            cards = getattr(self, "connect_cards", {}) or {}
            for instrument_id, widgets in cards.items():
                conn = widgets.get("connection") if isinstance(widgets, dict) else None
                if conn is None:
                    continue
                try:
                    conn.close()
                except Exception as e:
                    print(f"[{instrument_id}] Error closing connection: {e}")
                finally:
                    if isinstance(widgets, dict):
                        widgets["connection"] = None

            try:
                self.gui_funcs.cleanup()
                print("Application closed successfully")
            except Exception as e:
                print(f"Error during cleanup: {e}")
            finally:
                self.destroy()


    # --- Module-level helpers (extracted from daq_gui_func.plot_example_*) ---

    def plot_example_spec(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.set_xlabel("Charge(Vs)")
        self.ax.hist([1, 2, 3, 4, 5])
        self.canvas = FigureCanvasTkAgg(fig, self.liveplot)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

    def plot_example_wf(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig = Figure(figsize=(6, 4), dpi=100)
        a_x = fig.add_subplot(111)
        a_x.plot([1, 2, 3, 4, 5], [10, 10, 50, 40, 10])
        self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

    def plot_example_iv(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig = Figure(figsize=(6, 4), dpi=100)
        a_x = fig.add_subplot(111)
        a_x.set_xlabel('Voltios')
        a_x.set_ylabel('Amperios')
        a_x.plot([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        self.canvas = FigureCanvasTkAgg(fig, self.plotIV)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")


    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

except Exception as e:
    logging.error(str(e))

