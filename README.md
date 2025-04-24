# DAQ-Pyvisa

DAQ-Pyvisa is a graphical Python application designed for the data acquisition lab. It provides an easy-to-use interface to control the three oscilloscopes available in the lab and perform essential SiPM (Silicon Photomultiplier) tests.

## 🎯 Purpose

This tool is developed to simplify and automate basic characterization tests of SiPMs using laboratory equipment.

## ⚙️ Features

- **IV Curve Measurement (SMU)**  
  Automatically sweep and record current-voltage characteristics using a Source Measure Unit (SMU).

- **Charge Histogram**  
  Acquire and plot charge histograms from the oscilloscope to calculate either the Photon Detection Efficiency (PDE) or the amplification of the SiPM.

- **Waveform Capture**  
  Record and save raw waveforms continuously for the desired duration.

## 🧪 Equipment

- Compatible with the three lab oscilloscopes.
- Communication via **PyVISA** and **NI-VISA backend**.

## 📦 Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/FernandoFGF/DAQ-Pyvisa.git
   cd DAQ-Pyvisa
   pip install requirements.txt
