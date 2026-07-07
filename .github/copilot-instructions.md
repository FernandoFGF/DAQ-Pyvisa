## DAQ-Pyvisa — Quick guide for AI coding agents

This repo is a small desktop DAQ application (Tk/CustomTkinter) that drives lab instruments via PyVISA. After the refactor it has a layered architecture: GUI, facade, adapters, pure analysis, instruments.

### Entry points and key files

- `run_daq.py` / `run_daq.bat` — application launchers. `run_daq.py` does preflight checks on `config.yaml` / `.env` and then imports `daq_gui_main`.
- `daq_gui_main.py` — application entry. Creates the `App` (CustomTkinter) instance, redirects stdout/stderr into the UI textbox, configures theme and ties UI actions to methods on `self`. **Do not** import `daq_gui_func` (deleted). UI methods delegate to `self.gui_funcs` (a `gui_functions.DAQGUIFunctions` instance).
- `gui_functions.py` — `DAQGUIFunctions` facade. Spawns background threads for IV / spectrum / waveform acquisitions and exposes wrappers around `analysis/`. Use `self.gui_funcs.start_iv_full(...)`, `self.gui_funcs.start_spectrum_full(...)`, `self.gui_funcs.start_waveform_full(...)` from `App` methods. Use `self.gui_funcs.save_iv_results_to(name, path)` and `self.gui_funcs.save_spectrum_results_to(name, path)` for persistence.
- `daq_gui_iv.py`, `daq_gui_spec.py`, `daq_gui_wf.py` — tab-specific UI construction. They register widgets and, for the analysis buttons (Vbr, Qr, Complete, Finder peaks, DCR, slider +/−), call small helpers in this file that delegate to `analysis/`.
- `analysis/` — pure numpy / scipy / matplotlib. No I/O, no GUI. `iv_analysis.calculate_vbr / calculate_qr / plot_iv`, `spectrum_analysis.parse_hist_data / find_histogram_peaks / plot_histogram_with_peaks`, `waveform_analysis.calculate_dcr / load_waveform_file / count_files / make_time_axis / plot_waveform`.
- `acquisition/` — instrument I/O adapters. `connection.InstrumentConnection` is the minimal protocol; `connection.open_pyvisa` returns a real adapter in production. `iv_acquisition.IVAcquisition`, `spectrum_acquisition.SpectrumAcquisition`, `waveform_acquisition.WaveformAcquisition`, plus `save.py` for `save_iv_text / save_spectrum_text / write_waveform_file / write_waveform_metadata / create_zip / ensure_dir / remove_path`.
- `instruments/`, `controllers/` — the optional abstraction layer (kept around for non-GUI use cases). The runtime GUI does not use them at the moment; `DAQGUIFunctions` instantiates `IVController` / `SpectrumController` / `WaveformController` internally only as scaffolding. If you need to add features, prefer doing them in `acquisition/` and `analysis/`.
- `lab_module.py` — filesystem / beep / path helpers (`get_path(tab_name)`, `create_directory`, `delete_path`, `create_zip_archive`, `beep`, `initialize_instrument`, `wait_for_operation_complete`, `print_progress`, `current_time`). Output path pattern: `.../Output/<tab>/<YYYY-MM-DD>/`.
- `dictionary_SCPI.py` — SCPI command constants used by `acquisition/`.
- `config_loader.py` / `config.yaml` — YAML + .env configuration singleton (`get_config()`). Instrument addresses live under `instruments.<id>.address`.

### Data flow (high level)

```
App (CustomTkinter) ──> gui_functions.DAQGUIFunctions ──> acquisition/* (I/O)
                                                └──> analysis/*   (pure)
```

The GUI never talks to pyvisa directly. The adapters never touch Tk. The analysis never touches the filesystem. Each layer is testable in isolation.

### Conventions and gotchas

- All `App` methods that take user input must validate floats and integers before calling the facade.
- Acquisition callbacks are called from a worker thread. **Always** hop back to the Tk main loop with `self.after(0, lambda: ...)` before mutating widgets or `StringVar`s.
- The spectrum and waveform acquisition objects take a `progress_callback` and a `results_callback`. The waveform adapter also writes per-segment files; do not assume the data is in memory until `results_callback` fires.
- For output paths use `str(lm.get_path(tab_name)) + "/"`; for creating directories use `acquisition.save.ensure_dir`. The output is a directory per tab per day.
- Stdout/stderr are redirected to the GUI textbox in `daq_gui_main.py`. Avoid printing excessive debug info; consider `logging` (file: `error.log`) for persistent errors.
- Use `self.gui_funcs.<method>` to access the facade. Don't call acquisition objects directly from `App`.

### Editing patterns

- Add a new UI control to a tab: edit `daq_gui_<tab>.py` to create the widget, then bind its command to a small helper in the same file or a method on `App`. If the action does analysis, delegate to `analysis/<...>`. If it acquires data, call a method on `self.gui_funcs`.
- Add a new analysis: add a function to the relevant `analysis/<file>.py`, add parity tests in `tests/test_<file>.py`, expose a thin wrapper in `DAQGUIFunctions` if the GUI needs to call it.
- Add a new instrument command: add a constant to `dictionary_SCPI.py` and use it from `acquisition/<...>.py`. Write a test that uses `FakeConnection` to assert the command sequence.

### Testing

- Run the suite with: `python -m unittest discover -s tests -p "test_*.py"` (39 tests, no external deps).
- `tests/fake_connection.py` provides a `FakeConnection` that records `write`/`query` and lets you program responses. Use it in any new acquisition test.
- The `analysis/` parity tests re-implement the legacy algorithm verbatim and compare; keep them green when refactoring.

### Housekeeping

- Preserve the `StdoutRedirector` / `StderrRedirector` behaviour in `daq_gui_main.py` unless you intentionally change where messages appear.
- Keep error logging via `logging` (configured at top of `daq_gui_main.py` → `error.log`).
- New dependencies go in `requirements.txt`.
