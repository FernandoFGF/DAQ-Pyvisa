"""
Refactored GUI Functions Module

This module provides refactored GUI functions that use the new controller architecture.
It separates GUI logic from business logic and uses the new instrument and controller classes.

Author: Fernando Fuentes-Guerra
Date: 2025
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib import colors
from scipy.signal import find_peaks
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable

# Import new architecture components
from controllers.iv_controller import IVController
from controllers.spectrum_controller import SpectrumController
from controllers.waveform_controller import WaveformController
from instruments.instrument_manager import get_instrument_manager
from config_loader import get_config


class DAQGUIFunctions:
    """
    Refactored GUI functions class.
    
    This class provides GUI functions that use the new controller architecture.
    It separates GUI logic from business logic and provides better error handling.
    """
    
    def __init__(self):
        """Initialize the GUI functions class."""
        self.config = get_config()
        self.instrument_manager = get_instrument_manager()
        
        # Controllers
        self.iv_controller: Optional[IVController] = None
        self.spectrum_controller: Optional[SpectrumController] = None
        self.waveform_controller: Optional[WaveformController] = None
        
        # Threading control
        self.threads_active = {
            'iv': False,
            'spectrum': False,
            'waveform': False
        }
        
        # Callbacks for GUI updates
        self.gui_callbacks: Dict[str, List[Callable]] = {
            'progress': [],
            'data_ready': [],
            'error': []
        }
    
    def add_gui_callback(self, event_type: str, callback: Callable) -> None:
        """
        Add GUI callback function.
        
        Args:
            event_type: Type of event
            callback: Callback function
        """
        if event_type in self.gui_callbacks:
            self.gui_callbacks[event_type].append(callback)
    
    def _notify_gui(self, event_type: str, data: Any = None) -> None:
        """Notify GUI callbacks."""
        if event_type in self.gui_callbacks:
            for callback in self.gui_callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Error in GUI callback: {e}")
    
    # IV Measurement Functions
    
    def start_iv_measurement(self, v_start: float, v_stop: float, v_step: float, 
                           option: str = "SMU") -> None:
        """
        Start IV measurement sweep.
        
        Args:
            v_start: Start voltage
            v_stop: Stop voltage
            v_step: Voltage step
            option: Measurement option (SMU, etc.)
        """
        if self.threads_active['iv']:
            self._notify_gui('error', "IV measurement already in progress")
            return
        
        # Start measurement in thread
        self.threads_active['iv'] = True
        thread = threading.Thread(
            target=self._iv_measurement_thread,
            args=(v_start, v_stop, v_step, option)
        )
        thread.daemon = True
        thread.start()
    
    def _iv_measurement_thread(self, v_start: float, v_stop: float, 
                             v_step: float, option: str) -> None:
        """
        IV measurement thread function.
        
        Args:
            v_start: Start voltage
            v_stop: Stop voltage
            v_step: Voltage step
            option: Measurement option
        """
        try:
            # Create IV controller
            self.iv_controller = IVController("smu")
            
            # Connect to SMU
            self.iv_controller.connect_smu()
            
            # Setup measurement
            self.iv_controller.setup_measurement(
                channel=1,
                voltage_range=20.0,
                current_compliance=0.1,
                measurement_delay=0.1
            )
            
            # Calculate number of points
            num_points = int(abs(v_start - v_stop) / v_step)
            
            # Perform sweep
            voltage_array, current_array = self.iv_controller.iv_sweep(
                channel=1,
                start_voltage=v_start,
                stop_voltage=v_stop,
                num_points=num_points,
                delay=0.1,
                progress_callback=self._iv_progress_callback
            )
            
            # Store results
            self.iv_results = {
                'voltage_array': voltage_array,
                'current_array': current_array,
                'v_start': v_start,
                'v_stop': v_stop,
                'v_step': v_step,
                'option': option
            }
            
            # Notify GUI
            self._notify_gui('data_ready', self.iv_results)
            
        except Exception as e:
            self._notify_gui('error', f"IV measurement failed: {e}")
        finally:
            self.threads_active['iv'] = False
            if self.iv_controller:
                self.iv_controller.disconnect_smu()
    
    def _iv_progress_callback(self, progress: float) -> None:
        """IV measurement progress callback."""
        self._notify_gui('progress', progress)
    
    def stop_iv_measurement(self) -> None:
        """Stop IV measurement."""
        self.threads_active['iv'] = False
        if self.iv_controller:
            self.iv_controller.disconnect_smu()
    
    def save_iv_results(self, filename: str, path: Optional[str] = None) -> None:
        """
        Save IV measurement results.
        
        Args:
            filename: Output filename
            path: Optional output path
        """
        if not hasattr(self, 'iv_results'):
            self._notify_gui('error', "No IV results to save")
            return
        
        try:
            # Use provided path or default from config
            if path is None:
                output_dir = Path(self.config.get('paths', {}).get('output_dir', 'data'))
            else:
                output_dir = Path(path)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save data
            self.iv_controller.save_measurement_data(
                filename,
                self.iv_results['voltage_array'],
                self.iv_results['current_array'],
                metadata=self.iv_results
            )
            
            self._notify_gui('data_ready', f"IV results saved to {output_dir / filename}")
            
        except Exception as e:
            self._notify_gui('error', f"Failed to save IV results: {e}")
    
    def plot_iv_results(self, title: str = "IV Curve") -> Figure:
        """
        Plot IV measurement results.
        
        Args:
            title: Plot title
            
        Returns:
            Matplotlib figure
        """
        if not hasattr(self, 'iv_results'):
            raise ValueError("No IV results to plot")
        
        return self.iv_controller.plot_iv_curve(
            self.iv_results['voltage_array'],
            self.iv_results['current_array'],
            title
        )
    
    # Spectrum Measurement Functions
    
    def start_spectrum_measurement(self, num_points: int, scope: str = "1", 
                                 channel: str = "1") -> None:
        """
        Start spectrum measurement.
        
        Args:
            num_points: Number of data points
            scope: Oscilloscope identifier
            channel: Channel number
        """
        if self.threads_active['spectrum']:
            self._notify_gui('error', "Spectrum measurement already in progress")
            return
        
        # Start measurement in thread
        self.threads_active['spectrum'] = True
        thread = threading.Thread(
            target=self._spectrum_measurement_thread,
            args=(num_points, scope, channel)
        )
        thread.daemon = True
        thread.start()
    
    def _spectrum_measurement_thread(self, num_points: int, scope: str, 
                                   channel: str) -> None:
        """
        Spectrum measurement thread function.
        
        Args:
            num_points: Number of data points
            scope: Oscilloscope identifier
            channel: Channel number
        """
        try:
            # Create spectrum controller
            self.spectrum_controller = SpectrumController(f"scope{scope}")
            
            # Connect to oscilloscope
            self.spectrum_controller.connect_oscilloscope()
            
            # Setup measurement
            self.spectrum_controller.setup_spectrum_measurement(
                channel=int(channel),
                time_per_div=1e-3,
                voltage_scale=1.0,
                trigger_level=0.0
            )
            
            # Perform measurement
            results = self.spectrum_controller.measure_spectrum(
                channel=int(channel),
                window_type="hann",
                progress_callback=self._spectrum_progress_callback
            )
            
            # Store results
            self.spectrum_results = results
            
            # Notify GUI
            self._notify_gui('data_ready', self.spectrum_results)
            
        except Exception as e:
            self._notify_gui('error', f"Spectrum measurement failed: {e}")
        finally:
            self.threads_active['spectrum'] = False
            if self.spectrum_controller:
                self.spectrum_controller.disconnect_oscilloscope()
    
    def _spectrum_progress_callback(self, progress: float) -> None:
        """Spectrum measurement progress callback."""
        self._notify_gui('progress', progress)
    
    def stop_spectrum_measurement(self) -> None:
        """Stop spectrum measurement."""
        self.threads_active['spectrum'] = False
        if self.spectrum_controller:
            self.spectrum_controller.disconnect_oscilloscope()
    
    def save_spectrum_results(self, filename: str, path: Optional[str] = None) -> None:
        """
        Save spectrum measurement results.
        
        Args:
            filename: Output filename
            path: Optional output path
        """
        if not hasattr(self, 'spectrum_results'):
            self._notify_gui('error', "No spectrum results to save")
            return
        
        try:
            # Use provided path or default from config
            if path is None:
                output_dir = Path(self.config.get('paths', {}).get('output_dir', 'data'))
            else:
                output_dir = Path(path)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save data
            self.spectrum_controller.save_spectrum_data(filename)
            
            self._notify_gui('data_ready', f"Spectrum results saved to {output_dir / filename}")
            
        except Exception as e:
            self._notify_gui('error', f"Failed to save spectrum results: {e}")
    
    def plot_spectrum_results(self, title: str = "Spectrum Analysis") -> Figure:
        """
        Plot spectrum measurement results.
        
        Args:
            title: Plot title
            
        Returns:
            Matplotlib figure
        """
        if not hasattr(self, 'spectrum_results'):
            raise ValueError("No spectrum results to plot")
        
        return self.spectrum_controller.plot_spectrum(title)
    
    # Waveform Measurement Functions
    
    def start_waveform_measurement(self, scope: str = "1", channel: str = "1",
                                 num_averages: int = 1) -> None:
        """
        Start waveform measurement.
        
        Args:
            scope: Oscilloscope identifier
            channel: Channel number
            num_averages: Number of waveforms to average
        """
        if self.threads_active['waveform']:
            self._notify_gui('error', "Waveform measurement already in progress")
            return
        
        # Start measurement in thread
        self.threads_active['waveform'] = True
        thread = threading.Thread(
            target=self._waveform_measurement_thread,
            args=(scope, channel, num_averages)
        )
        thread.daemon = True
        thread.start()
    
    def _waveform_measurement_thread(self, scope: str, channel: str, 
                                   num_averages: int) -> None:
        """
        Waveform measurement thread function.
        
        Args:
            scope: Oscilloscope identifier
            channel: Channel number
            num_averages: Number of waveforms to average
        """
        try:
            # Create waveform controller
            self.waveform_controller = WaveformController(f"scope{scope}")
            
            # Connect to oscilloscope
            self.waveform_controller.connect_oscilloscope()
            
            # Setup measurement
            self.waveform_controller.setup_waveform_measurement(
                channel=int(channel),
                time_per_div=1e-3,
                voltage_scale=1.0,
                voltage_offset=0.0,
                trigger_level=0.0,
                trigger_slope="POS"
            )
            
            # Perform measurement
            results = self.waveform_controller.measure_waveform(
                channel=int(channel),
                num_averages=num_averages,
                progress_callback=self._waveform_progress_callback
            )
            
            # Store results
            self.waveform_results = results
            
            # Notify GUI
            self._notify_gui('data_ready', self.waveform_results)
            
        except Exception as e:
            self._notify_gui('error', f"Waveform measurement failed: {e}")
        finally:
            self.threads_active['waveform'] = False
            if self.waveform_controller:
                self.waveform_controller.disconnect_oscilloscope()
    
    def _waveform_progress_callback(self, progress: float) -> None:
        """Waveform measurement progress callback."""
        self._notify_gui('progress', progress)
    
    def stop_waveform_measurement(self) -> None:
        """Stop waveform measurement."""
        self.threads_active['waveform'] = False
        if self.waveform_controller:
            self.waveform_controller.disconnect_oscilloscope()
    
    def save_waveform_results(self, filename: str, path: Optional[str] = None) -> None:
        """
        Save waveform measurement results.
        
        Args:
            filename: Output filename
            path: Optional output path
        """
        if not hasattr(self, 'waveform_results'):
            self._notify_gui('error', "No waveform results to save")
            return
        
        try:
            # Use provided path or default from config
            if path is None:
                output_dir = Path(self.config.get('paths', {}).get('output_dir', 'data'))
            else:
                output_dir = Path(path)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save data
            self.waveform_controller.save_waveform_data(filename)
            
            self._notify_gui('data_ready', f"Waveform results saved to {output_dir / filename}")
            
        except Exception as e:
            self._notify_gui('error', f"Failed to save waveform results: {e}")
    
    def plot_waveform_results(self, title: str = "Waveform Analysis") -> Figure:
        """
        Plot waveform measurement results.
        
        Args:
            title: Plot title
            
        Returns:
            Matplotlib figure
        """
        if not hasattr(self, 'waveform_results'):
            raise ValueError("No waveform results to plot")
        
        return self.waveform_controller.plot_waveform(title)

    # --- Phase 3: analysis + acquisition glue (delegates to analysis/ and acquisition/) ---

    def start_iv_full(self, v_start: float, v_stop: float, v_step: float,
                      option: str = "SMU",
                      results_callback: Optional[Callable[[dict], None]] = None,
                      error_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Run an IV measurement in a background thread using IVAcquisition.

        The caller passes v_start/v_stop/v_step explicitly (instead of
        having the GUI helper read them from widgets) so this method
        stays independent of any specific Tk layout.

        On success, ``results_callback`` receives a dict with keys
        ``voltage``, ``current`` (numpy arrays) and ``points``.
        """
        from acquisition.iv_acquisition import IVAcquisition

        if self.threads_active['iv']:
            msg = "IV measurement already in progress"
            if error_callback:
                error_callback(msg)
            else:
                self._notify_gui('error', msg)
            return

        def _run():
            try:
                acq = IVAcquisition("smu", v_start=v_start, v_stop=v_stop,
                                    v_step=v_step, config=self.config.config)
                result = acq.run()
                payload = {
                    "voltage": result.voltage,
                    "current": result.current,
                    "points": result.points,
                }
                self.iv_results = payload
                if results_callback:
                    results_callback(payload)
                else:
                    self._notify_gui('data_ready', payload)
            except Exception as e:
                if error_callback:
                    error_callback(str(e))
                else:
                    self._notify_gui('error', f"IV measurement failed: {e}")
            finally:
                self.threads_active['iv'] = False

        self.threads_active['iv'] = True
        threading.Thread(target=_run, daemon=True).start()

    def start_spectrum_full(self, num_datos: int, scope: str, channel: str,
                            results_callback: Optional[Callable[[dict], None]] = None,
                            progress_callback: Optional[Callable[[np.ndarray], None]] = None,
                            error_callback: Optional[Callable[[str], None]] = None) -> None:
        """Run a spectrum (charge histogram) acquisition in a thread."""
        from acquisition.spectrum_acquisition import SpectrumAcquisition

        if self.threads_active['spectrum']:
            msg = "Spectrum measurement already in progress"
            if error_callback:
                error_callback(msg)
            else:
                self._notify_gui('error', msg)
            return

        def _on_progress(arr: np.ndarray) -> None:
            if progress_callback:
                progress_callback(arr)
            self._notify_gui('progress', float(len(arr)) / max(num_datos, 1) * 100.0)

        def _run():
            try:
                acq = SpectrumAcquisition(scope_id=scope, channel=channel,
                                          num_datos=num_datos,
                                          config=self.config.config)
                result = acq.run(progress_callback=_on_progress)
                payload = {
                    "data": result.data,
                    "scope": result.scope,
                    "channel": result.channel,
                    "num_datos": result.num_datos,
                }
                self.spectrum_results = payload
                if results_callback:
                    results_callback(payload)
                else:
                    self._notify_gui('data_ready', payload)
            except Exception as e:
                if error_callback:
                    error_callback(str(e))
                else:
                    self._notify_gui('error', f"Spectrum measurement failed: {e}")
            finally:
                self.threads_active['spectrum'] = False

        self.threads_active['spectrum'] = True
        threading.Thread(target=_run, daemon=True).start()

    def start_waveform_full(self, scope: str, channel: str, time_seconds: float,
                            name: str, save_root: str,
                            results_callback: Optional[Callable[[dict], None]] = None,
                            error_callback: Optional[Callable[[str], None]] = None) -> None:
        """Run a waveform acquisition in a thread."""
        from acquisition.waveform_acquisition import WaveformAcquisition

        if self.threads_active['waveform']:
            msg = "Waveform measurement already in progress"
            if error_callback:
                error_callback(msg)
            else:
                self._notify_gui('error', msg)
            return

        def _run():
            try:
                acq = WaveformAcquisition(scope_id=scope, channel=channel,
                                          time_seconds=time_seconds,
                                          save_root=save_root, name=name,
                                          config=self.config.config)
                result = acq.run()
                payload = {
                    "path_d": result.path_d,
                    "time_base": result.time_base,
                    "num_points": result.num_points,
                    "y_data": result.y_data,
                    "x_data": result.x_data,
                    "zip_path": result.zip_path,
                }
                self.waveform_results = payload
                if results_callback:
                    results_callback(payload)
                else:
                    self._notify_gui('data_ready', payload)
            except Exception as e:
                if error_callback:
                    error_callback(str(e))
                else:
                    self._notify_gui('error', f"Waveform measurement failed: {e}")
            finally:
                self.threads_active['waveform'] = False

        self.threads_active['waveform'] = True
        threading.Thread(target=_run, daemon=True).start()

    # --- Result persistence (delegates to acquisition.save) ---

    def save_iv_results_to(self, name: str, path: str) -> None:
        """Save the last IV result to ``<path><name>.txt``."""
        from acquisition.save import save_iv_text

        if not hasattr(self, 'iv_results') or self.iv_results is None:
            self._notify_gui('error', "No IV results to save")
            return
        v = self.iv_results['voltage']
        i = self.iv_results['current']
        save_iv_text(path + name, v, i)
        self._notify_gui('data_ready', f"IV saved to {path}{name}.txt")

    def save_spectrum_results_to(self, name: str, path: str) -> None:
        """Save the last spectrum result to ``<path><name>.txt``."""
        from acquisition.save import save_spectrum_text

        if not hasattr(self, 'spectrum_results') or self.spectrum_results is None:
            self._notify_gui('error', "No spectrum results to save")
            return
        save_spectrum_text(path, name, self.spectrum_results['data'])
        self._notify_gui('data_ready', f"Spectrum saved to {path}{name}.txt")

    # --- Analysis helpers (delegates to analysis/) ---

    def vbr_for(self, v_values, i_values) -> dict:
        from analysis.iv_analysis import calculate_vbr
        return calculate_vbr(np.asarray(v_values, dtype=float),
                             np.asarray(i_values, dtype=float))

    def qr_for(self, v_values, i_values) -> dict:
        from analysis.iv_analysis import calculate_qr
        return calculate_qr(np.asarray(v_values, dtype=float),
                            np.asarray(i_values, dtype=float))

    def plot_iv(self, ax, v_values, i_values, vbr_point=None, qr_line=None,
                dydx_over_y=None, v_for_ratio=None) -> None:
        from analysis.iv_analysis import plot_iv
        plot_iv(ax, v_values, i_values, vbr_point=vbr_point, qr_line=qr_line,
                dydx_over_y=dydx_over_y, v_for_ratio=v_for_ratio)

    def find_histogram_peaks(self, data, bins: int = 50, prominence: float = 80) -> dict:
        from analysis.spectrum_analysis import find_histogram_peaks as _fhp
        return _fhp(np.asarray(data, dtype=float), bins=bins, prominence=prominence)

    def plot_histogram_with_peaks(self, ax, data, peaks_result=None) -> dict:
        from analysis.spectrum_analysis import plot_histogram_with_peaks as _phwp
        return _phwp(ax, np.asarray(data, dtype=float), peaks_result=peaks_result)

    def calculate_dcr(self, num_files: int, time_str: str) -> dict:
        from analysis.waveform_analysis import calculate_dcr as _dcr
        return _dcr(num_files, time_str)

    def count_waveform_files(self, path: str, prefix: str):
        from analysis.waveform_analysis import count_files
        return count_files(path, prefix)

    def load_waveform_file(self, path: str, skip_lines: int = 2):
        from analysis.waveform_analysis import load_waveform_file as _lwf
        return _lwf(path, skip_lines=skip_lines)

    def make_waveform_time_axis(self, num_points: int, length: int = 1000):
        from analysis.waveform_analysis import make_time_axis
        return make_time_axis(num_points, length=length)

    def plot_waveform(self, ax, data, num_points: int, length: int = 1000) -> None:
        from analysis.waveform_analysis import plot_waveform as _pwf
        _pwf(ax, data, num_points=num_points, length=length)

    # Utility Functions
    
    def save_plot_as_png(self, figure: Figure, filename: str, 
                        path: Optional[str] = None) -> None:
        """
        Save matplotlib figure as PNG.
        
        Args:
            figure: Matplotlib figure
            filename: Output filename
            path: Optional output path
        """
        try:
            # Use provided path or default from config
            if path is None:
                output_dir = Path(self.config.get('paths', {}).get('output_dir', 'data'))
            else:
                output_dir = Path(path)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save figure
            output_path = output_dir / f"{filename}.png"
            figure.savefig(output_path, dpi=300, bbox_inches='tight')
            
            self._notify_gui('data_ready', f"Plot saved to {output_path}")
            
        except Exception as e:
            self._notify_gui('error', f"Failed to save plot: {e}")
    
    def get_instrument_status(self) -> Dict[str, Any]:
        """
        Get status of all instruments.
        
        Returns:
            Dictionary with instrument status information
        """
        return self.instrument_manager.get_all_instrument_info()
    
    def connect_all_instruments(self) -> None:
        """Connect to available instruments (one at a time is fine)."""
        try:
            # Get instrument configuration
            instruments_config = self.config.get('instruments', {})
            
            if not instruments_config:
                self._notify_gui('error', "No instruments configured in config.yaml")
                return
            
            connected_count = 0
            total_count = len(instruments_config)
            connected_instruments = []
            
            print(f"Attempting to connect to {total_count} configured instruments...")
            
            for instrument_id, instrument_config in instruments_config.items():
                try:
                    # Create instrument
                    instrument_type = instrument_config.get('type', instrument_id)
                    instrument = self.instrument_manager.create_instrument(
                        instrument_type, instrument_id
                    )
                    
                    # Connect instrument
                    self.instrument_manager.connect_instrument(instrument_id)
                    connected_count += 1
                    connected_instruments.append(instrument_id)
                    print(f"✓ Connected to {instrument_id} at {instrument_config.get('address', 'unknown')}")
                    
                except Exception as e:
                    error_msg = str(e)
                    if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                        print(f"✗ {instrument_id}: Not available (not powered on or network issue)")
                    else:
                        print(f"✗ {instrument_id}: {error_msg}")
            
            # Provide helpful feedback
            if connected_count == 0:
                print("\n❌ No instruments could be connected.")
                print("This is normal if:")
                print("  • Only one instrument is connected at a time")
                print("  • Instruments are not powered on")
                print("  • Network connections are not established")
                print("  • IP addresses in config.yaml need updating")
                print("\n💡 Tip: You can still use the application with simulated data")
                self._notify_gui('data_ready', "No instruments connected - you can still use the application")
            elif connected_count == 1:
                print(f"\n✅ Connected to 1 instrument: {connected_instruments[0]}")
                print("This is perfect for single-instrument operation!")
                self._notify_gui('data_ready', f"Connected to {connected_instruments[0]} - ready for measurements")
            else:
                print(f"\n✅ Connected to {connected_count} instruments: {', '.join(connected_instruments)}")
                self._notify_gui('data_ready', f"Connected to {connected_count} instruments")
            
        except Exception as e:
            self._notify_gui('error', f"Configuration error: {e}")
    
    def connect_specific_instrument(self, instrument_id: str) -> bool:
        """
        Connect to a specific instrument.
        
        Args:
            instrument_id: ID of the instrument to connect
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get instrument configuration
            instruments_config = self.config.get('instruments', {})
            
            if instrument_id not in instruments_config:
                print(f"✗ Instrument '{instrument_id}' not found in configuration")
                return False
            
            instrument_config = instruments_config[instrument_id]
            
            # Create and connect instrument
            instrument_type = instrument_config.get('type', instrument_id)
            instrument = self.instrument_manager.create_instrument(
                instrument_type, instrument_id
            )
            
            self.instrument_manager.connect_instrument(instrument_id)
            print(f"✓ Connected to {instrument_id} at {instrument_config.get('address', 'unknown')}")
            self._notify_gui('data_ready', f"Connected to {instrument_id}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                print(f"✗ Failed to connect {instrument_id}: Instrument not available")
            else:
                print(f"✗ Failed to connect {instrument_id}: {error_msg}")
            return False
    
    def disconnect_all_instruments(self) -> None:
        """Disconnect from all instruments."""
        try:
            self.instrument_manager.disconnect_all()
            self._notify_gui('data_ready', "All instruments disconnected")
        except Exception as e:
            self._notify_gui('error', f"Failed to disconnect instruments: {e}")
    
    def stop_all_measurements(self) -> None:
        """Stop all active measurements."""
        self.stop_iv_measurement()
        self.stop_spectrum_measurement()
        self.stop_waveform_measurement()
        self._notify_gui('data_ready', "All measurements stopped")
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.stop_all_measurements()
        self.disconnect_all_instruments()
        self.instrument_manager.clear_all()

