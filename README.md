# DAQ-Pyvisa: Laboratory Data Acquisition System

A Python-based data acquisition system for laboratory instruments, built on PyVISA. The architecture separates pure data analysis, instrument I/O and the GUI so each layer can be tested and evolved independently.

## Features

- **Layered architecture**: GUI → facade (`gui_functions.DAQGUIFunctions`) → adapters (`acquisition/`) + pure analysis (`analysis/`).
- **Instruments**: oscilloscopes (RTA, RTO, Keysight dialects) and SMU; extensible through `instruments/`.
- **Measurement types**: IV curves, spectrum (charge histogram), waveform (segmented capture).
- **GUI**: CustomTkinter with IV / Spectrum / Waveform tabs and per-tab Analysis sub-tab.
- **Tested**: 39 unit tests covering analysis parity with the legacy algorithm and acquisition adapter behaviour against a `FakeConnection`.

## Requirements

- Python 3.8+
- Windows 10/11 (tested on Windows 10)
- VISA drivers (NI-VISA or Keysight IO Libraries)
- See `requirements.txt`.

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `config.yaml` to match the VISA addresses of your instruments.

## Usage

### Start the application

```bash
run_daq.bat          # Windows convenience launcher
# or
python run_daq.py    # Python launcher with preflight checks
# or
python daq_gui_main.py
```

### GUI flow

1. Click **Connect All Instruments** (or the per-instrument buttons).
2. Pick a tab (IV Curves / Spectrum / Waveform).
3. Set the parameters and click **Start**. The measurement runs in a background thread; the GUI updates as data arrives.
4. Use the **Analysis** sub-tab to run Vbr, Qr, peak finder, DCR or slider navigation over the captured data.
5. Use the option-frame buttons (**Save results**, **Print results**, **Open folder**) to persist the data.

### Programmatic use

```python
from analysis.iv_analysis import calculate_vbr, calculate_qr
from acquisition.iv_acquisition import IVAcquisition
from tests.fake_connection import FakeConnection  # or use acquisition.connection.open_pyvisa

# Pure analysis
result = calculate_vbr(voltage_array, current_array)
print(result["max_x"])

# Acquisition with a fake connection (for tests)
fake = FakeConnection()
fake.set_response(":FETC:ARR:CURR?", "0.1,0.2,0.3")
fake.set_response(":FETC:ARR:VOLT?", "1.0,0.5,0.0")
fake.set_response("*OPC?", "1")
acq = IVAcquisition("smu", v_start=1.0, v_stop=0.0, v_step=0.5)
acq.set_connection(fake)
out = acq.run()
```

## Project structure

```
DAQ-Pyvisa/
├── daq_gui_main.py             # CustomTkinter App, entry point
├── daq_gui_iv.py               # IV tab UI + Vbr/Qr/Complete wiring
├── daq_gui_spec.py             # Spectrum tab UI + Finder peaks wiring
├── daq_gui_wf.py               # Waveform tab UI + DCR/slider wiring
├── gui_functions.py            # DAQGUIFunctions facade (used by the App)
├── lab_module.py               # Path / file / instrument helpers
├── config_loader.py            # YAML + .env configuration singleton
├── config.yaml                 # Instrument addresses and constants
├── analysis/                   # Pure numpy/matplotlib analysis (no I/O)
│   ├── iv_analysis.py          # calculate_vbr, calculate_qr, plot_iv
│   ├── spectrum_analysis.py    # find_histogram_peaks, plot_histogram_with_peaks
│   └── waveform_analysis.py    # calculate_dcr, load_waveform_file, count_files, plot_waveform
├── acquisition/                # Instrument I/O adapters
│   ├── connection.py           # InstrumentConnection protocol + open_pyvisa factory
│   ├── save.py                 # save_iv_text, save_spectrum_text, write_waveform_file, etc.
│   ├── iv_acquisition.py       # SMU voltage sweep
│   ├── spectrum_acquisition.py # Charge histogram (3 oscilloscope dialects)
│   └── waveform_acquisition.py # Segmented waveform capture (3 oscilloscope dialects)
├── instruments/                # Optional abstraction layer (connect / disconnect)
│   ├── base_instrument.py
│   ├── smu.py
│   ├── oscilloscope.py
│   └── instrument_manager.py
├── controllers/                # Optional high-level controllers (FFT, etc.)
│   ├── iv_controller.py
│   ├── spectrum_controller.py
│   └── waveform_controller.py
├── tests/                      # unittest suite (39 tests)
│   ├── fake_connection.py      # In-memory connection with programmed responses
│   ├── test_iv_analysis.py     # Parity vs legacy Vbr/Qr
│   ├── test_spectrum_analysis.py
│   ├── test_waveform_analysis.py
│   ├── test_acquisition_iv.py
│   ├── test_acquisition_spectrum.py
│   ├── test_acquisition_waveform.py
│   └── test_acquisition_save.py
└── dictionary_SCPI.py          # SCPI command constants (used by acquisition/)
```

## Architecture

The data flow is intentionally one-way:

```
App (CustomTkinter) ──> gui_functions.DAQGUIFunctions ──> acquisition/ (I/O)
                                                └──> analysis/   (pure)
```

- **acquisition/** talks to instruments through an `InstrumentConnection` (pyvisa in production, `FakeConnection` in tests). The adapters preserve the legacy SCPI dialect per oscilloscope model (RTA, RTO, Keysight).
- **analysis/** is pure numpy / scipy / matplotlib; no I/O, no GUI. Parity tests verify that the analysis behaves exactly like the original `daq_gui_func.start_vbr / start_qr / finding_peaks / start_dcr` did.
- **gui_functions.py** is the facade: it spawns acquisition threads, marshals results back to the Tk main loop, and exposes small wrappers for the analysis functions.
- **instruments/** and **controllers/** are the original optional abstraction layers (kept for future use, e.g. when the same measurements are needed without the Tk GUI).

## Testing

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The test suite covers the analysis parity and the acquisition adapters' SCPI command sequences and output files, all without requiring real hardware.

## Troubleshooting

- **App won't start with `ModuleNotFoundError: dotenv`** — make sure the venv is activated before running.
- **`Cannot connect to <instrument>`** — verify the address in `config.yaml` and that the instrument is powered on and reachable.
- **No data appears after a measurement** — check the textbox (the GUI captures stdout) and `error.log` at the project root.

## License

MIT.

## Author

Fernando Fuentes-Guerra.

## Acknowledgments

PyVISA community, CustomTkinter, National Instruments and Keysight for VISA drivers.
