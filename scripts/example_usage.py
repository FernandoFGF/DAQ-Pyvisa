"""
Example usage of the DAQ-Pyvisa API (acquisition/ + analysis/).

Run with: ``python -m scripts.example_usage`` (from the project
root). The examples need a real instrument reachable at the
addresses in config.yaml; they print the progress and exit when
the measurements finish.
"""

import matplotlib.pyplot as plt
from pathlib import Path

from acquisition.iv_acquisition import IVAcquisition
from acquisition.spectrum_acquisition import SpectrumAcquisition
from acquisition.waveform_acquisition import WaveformAcquisition
from analysis.iv_analysis import calculate_vbr, calculate_qr, plot_iv
from analysis.spectrum_analysis import find_histogram_peaks, plot_histogram_with_peaks
from analysis.waveform_analysis import load_waveform_file, plot_waveform
from config_loader import get_config


config = get_config()


def example_iv_measurement() -> None:
    print("=== IV Measurement Example ===")
    acq = IVAcquisition("smu", v_start=1.0, v_stop=-10.0, v_step=0.1,
                       config=config.config)
    voltage, current = acq.run()
    print(f"Acquired {len(voltage)} points: {voltage[:3]} V -> {current[:3]} A")

    vbr = calculate_vbr(voltage, current)
    qr = calculate_qr(voltage, current)
    if vbr.get("ok"):
        print(f"Vbr = {vbr['max_x']} V")
    if qr.get("ok"):
        print(f"Qr  = {qr['qr_value']} Ohm")

    fig, ax = plt.subplots()
    plot_iv(ax, voltage, current)
    plt.show()


def example_spectrum_measurement() -> None:
    print("=== Spectrum Measurement Example ===")
    acq = SpectrumAcquisition(scope_id="1", channel="MA1", num_datos=500,
                              config=config.config)
    data = acq.run()
    print(f"Acquired {len(data.data)} charge samples")

    peaks = find_histogram_peaks(data.data, bins=50, prominence=80)
    if peaks.get("ok"):
        print(f"Detected {len(peaks['peak_indices'])} peaks")

    fig, ax = plt.subplots()
    plot_histogram_with_peaks(ax, data.data, peaks_result=peaks)
    plt.show()


def example_waveform_measurement() -> None:
    print("=== Waveform Measurement Example ===")
    save_root = str(config.get_output_path("waveform") / "2024-01-01")
    acq = WaveformAcquisition(scope_id="1", channel="1", time_seconds=0.5,
                              save_root=save_root, name="demo",
                              config=config.config)
    result = acq.run()
    print(f"Captured {result.num_points} points at {result.path_d}")

    # Reload the first segment and plot it.
    first_segment = Path(result.path_d) / "demo_0.txt"
    if first_segment.exists():
        data = load_waveform_file(str(first_segment))
        fig, ax = plt.subplots()
        plot_waveform(ax, data, num_points=result.num_points)
        plt.show()


if __name__ == "__main__":
    example_iv_measurement()
    example_spectrum_measurement()
    example_waveform_measurement()
