# Migration Guide

> **Status (2025): completed.** The refactor described below is finished. The legacy `daq_gui_func.py` module and the deprecated `lab_module` aliases have been removed; the new layered architecture (`analysis/`, `acquisition/`, `gui_functions.DAQGUIFunctions`) is what the GUI uses today.

This document is kept as a historical record of the migration. For the current project structure, see `README.md` and `.github/copilot-instructions.md`.

## What changed

- The legacy `daq_gui_func.py` (≈ 1059 lines of measurement routines, plotting helpers, file I/O, and analysis mixed together) is gone. Its responsibilities were split:
  - **Pure analysis** (Vbr, Qr, finding peaks, DCR, waveform file loading) moved to `analysis/`.
  - **Instrument I/O** (SMU voltage sweep, scope spectrum histogram, scope waveform segmented capture) moved to `acquisition/`. The three oscilloscope dialects (RTA, RTO, Keysight) are preserved inside `SpectrumAcquisition` and `WaveformAcquisition`.
  - **GUI bridge** (threading, callbacks, save/plot helpers) lives in `gui_functions.DAQGUIFunctions`.
- The 13 deprecated `lab_module` aliases (`path`, `create_dir`, `delete_dir`, `create_zip`, `counter_finish`, `create_data`, `file_writer_wf`, `currentTime`, `waiting`, `init_pyvisa`, `file_writer_iv`, `chronometter`, `create_dir_in`) have been deleted. Use the new names directly (`get_path`, `create_directory`, `delete_path`, `create_zip_archive`, `print_progress`, `create_data_file`, `write_waveform_file`, `current_time`, `wait_for_operation_complete`, `initialize_instrument`, `write_iv_data_file`, `run_chronometer`).

## How the new code is wired

```
App (CustomTkinter) ──> gui_functions.DAQGUIFunctions ──> acquisition/* (I/O)
                                                └──> analysis/*   (pure)
```

Each layer is testable in isolation: `analysis/` is verified by parity tests against the legacy algorithm; `acquisition/` is verified with a `FakeConnection` that records every SCPI write/query.

## What was preserved

- The exact SCPI command sequences that the legacy code sent to each instrument type (RTA / RTO / Keysight for the scopes, the SMU stepped voltage sweep for the SMU).
- The same magic numbers (Vbr threshold -0.01, Qr threshold 0.75, peak prominence 80, histogram bins 50, time-axis 10x/12x scaling per scope).
- The `Output/<tab>/<YYYY-MM-DD>/` file layout, the segmented capture + per-segment file + zip + `DATA.txt` workflow for waveforms, and the `error.log` at the project root.
- The user-visible behaviour: every button on every tab does exactly what it did before.

## Original guide (historical)

The remainder of this file is the original migration guide, kept for reference.

---

# Migration Guide: From Legacy to New Architecture

This guide helps you migrate from the legacy DAQ-Pyvisa system to the new object-oriented architecture.

## What's New

### Architecture Improvements
- **Object-Oriented Design**: Clean separation of concerns
- **Configuration Management**: YAML-based configuration with environment variables
- **Instrument Classes**: Dedicated classes for different instrument types
- **Controller Pattern**: Separate controllers for different measurement types
- **Better Error Handling**: Comprehensive error handling and logging
- **Threading Support**: Non-blocking measurements with progress callbacks

### New Features
- **Automatic Data Saving**: Multiple formats (JSON, CSV, PNG)
- **Progress Callbacks**: Real-time progress updates
- **Context Managers**: Automatic resource management
- **Extensible Design**: Easy to add new instruments and measurements

## Migration Steps

### 1. Update Configuration

**Before (Legacy):**
```python
# Hardcoded paths and settings
smu = lm.init_pyvisa("smu")
```

**After (New):**
```yaml
# config.yaml
instruments:
  smu:
    type: smu
    address: TCPIP0::192.168.1.100::inst0::INSTR
    name: "Keysight B2902A SMU"
    timeout: 10000
```

```python
# config_loader.py handles configuration
from config_loader import get_config
config = get_config()
```

### 2. Update Instrument Usage

**Before (Legacy):**
```python
# Direct PyVISA usage
smu = lm.init_pyvisa("smu")
smu.write(":SOUR:VOLT 5.0")
result = smu.query(":MEAS:CURR?")
```

**After (New):**
```python
# Object-oriented approach
from instruments.smu import SMU

with SMU("smu") as smu:
    smu.set_output(1, 5.0, "VOLT")
    voltage, current = smu.measure_iv(1)
```

### 3. Update Measurement Logic

**Before (Legacy):**
```python
# Manual measurement setup
def start_iv(self):
    smu = lm.init_pyvisa("smu")
    smu.write(":SOUR:VOLT:STAR 0")
    smu.write(":SOUR:VOLT:STOP 10")
    # ... manual sweep implementation
```

**After (New):**
```python
# Controller-based approach
from controllers.iv_controller import IVController

with IVController("smu") as iv_ctrl:
    voltage, current = iv_ctrl.iv_sweep(
        channel=1,
        start_voltage=0.0,
        stop_voltage=10.0,
        num_points=100
    )
```

### 4. Update GUI Integration

**Before (Legacy):**
```python
# Direct GUI manipulation
def start_iv(self):
    self.start_button.configure(state="disabled")
    # ... measurement logic
    self.start_button.configure(state="normal")
```

**After (New):**
```python
# Callback-based approach
from gui_functions import DAQGUIFunctions

gui_funcs = DAQGUIFunctions()
gui_funcs.add_gui_callback('progress', self.update_progress)
gui_funcs.add_gui_callback('data_ready', self.update_data)
gui_funcs.start_iv_full(v_start, v_stop, v_step, option,
                        results_callback=..., error_callback=...)
```

## Code Migration Examples

### IV Measurement Migration

**Legacy Code:**
```python
def start_iv(self):
    smu = lm.init_pyvisa("smu")
    del smu.timeout
    smu.write(ds.rst)
    smu.write(ds.voltMode)
    smu.write(f":SOUR:VOLT:STAR {v_start}")
    smu.write(f":SOUR:VOLT:STOP {v_stop}")
    # ... manual sweep implementation
    i_result = smu.query(ds.queryCurr)
    v_result = smu.query(ds.queryVolt)
    smu.write(ds.smuOff)
```

**New Code:**
```python
def start_iv(self):
    self.gui_funcs.start_iv_full(
        v_start=v_start,
        v_stop=v_stop,
        v_step=v_step,
        option="SMU",
        results_callback=self._on_iv_results,
        error_callback=self._on_iv_error,
    )
```

### Spectrum Analysis Migration

**Legacy Code:**
```python
def start_spectrum(self):
    scope = lm.init_pyvisa("scope" + scope)
    for i in range(1, num_datos + 1):
        # ... manual data acquisition
        p_1 = float(scope.query(ds.posC1))
        p_2 = float(scope.query(ds.posC2))
        r_r = p_1 - p_2
        # ... manual histogram update
```

**New Code:**
```python
def start_spectrum(self):
    self.gui_funcs.start_spectrum_full(
        num_datos=num_datos,
        scope=scope,
        channel=channel,
        results_callback=self._on_spectrum_results,
        progress_callback=self._on_spectrum_progress,
    )
```

### Data Saving Migration

**Legacy Code:**
```python
def save_results_iv(self, path):
    v_values = self.v_values_aux.get()
    i_values = self.i_values_aux.get()
    lm.file_writer_iv(v_values, i_values, path)
```

**New Code:**
```python
def save_results(self):
    self.gui_funcs.save_iv_results_to(name, path)
    # or
    self.gui_funcs.save_spectrum_results_to(name, path)
```

## Data Format Changes

### Legacy Data Format
```
# Simple text files
voltage,current
0.0,0.001
0.1,0.002
...
```

### New Data Format
- **IV**: two lines, voltage space-separated then current space-separated (same as legacy).
- **Spectrum**: first line `min max`, then space-separated values.
- **Waveform**: per-segment file with TSR + wavedata header + one float per line; companion `DATA.txt` with time_base, num_points, scope id; `.zip` archive of the run folder.

## Troubleshooting Migration

### Common Issues

**Import Errors:**
```python
# Old imports
import lab_module as lm
import dictionary_SCPI as ds

# New imports
from acquisition.iv_acquisition import IVAcquisition
from analysis.iv_analysis import calculate_vbr
```

**Function Signature Changes:**
```python
# Old function signatures
def start_iv(self):
    # Uses self attributes

# New function signatures
def start_iv(self):
    # Reads widgets, calls self.gui_funcs.start_iv_full(...)

# Old save
lm.file_writer_iv(v, i, path)

# New save
self.gui_funcs.save_iv_results_to(name, path)
```

### Testing Migration

1. **Test Configuration:**
```python
from config_loader import get_config
config = get_config()
print("Configuration loaded successfully")
```

2. **Test Acquisition (with fake connection):**
```python
from acquisition.iv_acquisition import IVAcquisition
from tests.fake_connection import FakeConnection
fake = FakeConnection()
fake.set_response("*OPC?", "1")
fake.set_response(":FETC:ARR:CURR?", "0.1,0.2,0.3")
fake.set_response(":FETC:ARR:VOLT?", "1.0,0.5,0.0")
acq = IVAcquisition("smu", v_start=1.0, v_stop=0.0, v_step=0.5)
acq.set_connection(fake)
result = acq.run()
```

3. **Test Measurement:**
```python
from analysis.iv_analysis import calculate_vbr
result = calculate_vbr([1.0, 0.5, -5.0, -10.0], [1e-6, 5e-7, -1e-7, -1e-3])
print(result["max_x"])
```

## Benefits of Migration

### Performance Improvements
- **Faster Startup**: Configuration loaded once
- **Better Memory Management**: Context managers handle resources
- **Efficient Data Processing**: Optimized algorithms

### Maintainability
- **Modular Design**: Easy to modify individual components
- **Clear Separation**: GUI logic separated from business logic
- **Extensible**: Easy to add new instruments and measurements

### User Experience
- **Progress Updates**: Real-time progress feedback
- **Better Error Messages**: Clear error descriptions
- **Automatic Data Saving**: Multiple formats and locations

## Migration Checklist

- [x] Install new dependencies: `pip install -r requirements.txt`
- [x] Create `config.yaml` with instrument configurations
- [x] Create `.env` file with local paths
- [x] Update import statements
- [x] Replace direct PyVISA calls with `acquisition/` adapters
- [x] Replace manual measurements with adapter-driven flows
- [x] Update GUI integration to use callbacks
- [x] Test all measurement types (parity + adapter tests)
- [x] Verify data saving functionality
- [x] Update documentation (`README.md`, `.github/copilot-instructions.md`)

## Support

For current usage, see `README.md`. For historical context, this file is kept intact.
