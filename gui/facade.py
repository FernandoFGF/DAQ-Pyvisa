"""
GUI facade.

The bridge between the Tk-based application (daq_gui_main) and
the rest of the architecture: ``acquisition/`` for instrument I/O,
``analysis/`` for pure data analysis, and ``config_loader`` for
settings.

Only the methods actually called by the GUI are exposed; the
legacy controller-based surface was removed when the acquisition
adapters took over.
"""

import threading
from typing import Any, Callable, Dict, List, Optional

from config_loader import get_config


class DAQGUIFunctions:
    """Bridge between the App (da``q_gui_main``) and acquisition/analysis."""

    def __init__(self) -> None:
        self.config = get_config()
        self.threads_active = {"iv": False, "spectrum": False, "waveform": False}
        self.gui_callbacks: Dict[str, List[Callable]] = {
            "progress": [],
            "data_ready": [],
            "error": [],
        }

    # --- Callback plumbing -------------------------------------------------

    def add_gui_callback(self, event_type: str, callback: Callable) -> None:
        if event_type in self.gui_callbacks:
            self.gui_callbacks[event_type].append(callback)

    def _notify_gui(self, event_type: str, data: Any = None) -> None:
        for callback in self.gui_callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Error in GUI callback: {e}")

    # --- Acquisition (delegates to acquisition/) --------------------------

    def start_iv_full(self, v_start: float, v_stop: float, v_step: float,
                      option: str = "SMU",
                      smu_conn=None,
                      channel: int = 1,
                      results_callback: Optional[Callable[[dict], None]] = None,
                      error_callback: Optional[Callable[[str], None]] = None) -> None:
        """Run an IV measurement in a background thread using IVAcquisition.

        ``smu_conn`` is the live ``InstrumentConnection`` opened by the
        Connect tab for the SMU. When provided the adapter reuses it
        via ``set_connection`` so we do not open a second VISA session
        on top of the one the Connect card is holding. When ``None``
        (legacy behaviour) the adapter opens its own connection.

        ``channel`` selects the SMU channel (1 or 2). The Keithley
        2470 needs the channel selector on the :init and :FETCh
        commands; without it the SMU errors with a Settings conflict
        and returns a single value instead of the full sweep.
        """

        from acquisition.iv_acquisition import IVAcquisition

        if self.threads_active["iv"]:
            msg = "IV measurement already in progress"
            self._dispatch_error(msg, error_callback)
            return

        def _run():
            try:
                acq = IVAcquisition("smu", v_start=v_start, v_stop=v_stop,
                                    v_step=v_step, config=self.config.config,
                                    channel=channel)
                if smu_conn is not None:
                    acq.set_connection(smu_conn)
                result = acq.run()
                payload = {
                    "voltage": result.voltage,
                    "current": result.current,
                    "points": result.points,
                }
                self.iv_results = payload
                self._dispatch_result(payload, results_callback)
            except Exception as e:
                self._dispatch_error(f"IV measurement failed: {e}", error_callback)
            finally:
                self.threads_active["iv"] = False

        self.threads_active["iv"] = True
        threading.Thread(target=_run, daemon=True).start()

    def start_spectrum_full(self, num_datos: int, scope: str, channel: str,
                            instrument_id: Optional[str] = None,
                            scope_conn=None,
                            results_callback: Optional[Callable[[dict], None]] = None,
                            progress_callback: Optional[Callable[[Any], None]] = None,
                            error_callback: Optional[Callable[[str], None]] = None) -> None:
        """Run a spectrum (charge histogram) acquisition in a thread.

        ``scope`` is the SCPI dialect id (``"1"``=RTA, ``"2"``=RTO,
        ``"3"``=KEY). ``instrument_id`` is the actual VISA resource
        id (``"scope1"``/``"scope2"``/``"scope3"``); when omitted the
        adapter falls back to ``f"scope{scope}"`` for backwards
        compatibility with the legacy hard-coded mapping.

        ``scope_conn`` is the live ``InstrumentConnection`` opened by
        the Connect tab. When provided the adapter reuses it via
        ``set_connection`` so we do not open a second VISA session on
        top of the one the Connect card is holding (which previously
        caused duplicate sessions and made the scope flaky). When
        ``None`` (legacy / test behaviour) the adapter opens its own
        connection.
        """
        from acquisition.spectrum_acquisition import SpectrumAcquisition

        if self.threads_active["spectrum"]:
            msg = "Spectrum measurement already in progress"
            self._dispatch_error(msg, error_callback)
            return

        actual_instrument_id = instrument_id or f"scope{scope}"

        def _on_progress(arr) -> None:
            if progress_callback:
                progress_callback(arr)
            self._notify_gui("progress", float(len(arr)) / max(num_datos, 1) * 100.0)

        def _run():
            try:
                acq = SpectrumAcquisition(scope_id=scope, channel=channel,
                                          instrument_id=actual_instrument_id,
                                          num_datos=num_datos,
                                          config=self.config.config)
                if scope_conn is not None:
                    acq.set_connection(scope_conn)
                # Expose the live adapter so the GUI can request a
                # cooperative stop via ``request_stop()``.
                self._spectrum_acq = acq
                result = acq.run(progress_callback=_on_progress)
                payload = {
                    "data": result.data,
                    "scope": result.scope,
                    "channel": result.channel,
                    "num_datos": result.num_datos,
                }
                self.spectrum_results = payload
                self._dispatch_result(payload, results_callback)
            except Exception as e:
                self._dispatch_error(f"Spectrum measurement failed: {e}", error_callback)
            finally:
                self.threads_active["spectrum"] = False
                self._spectrum_acq = None

        self.threads_active["spectrum"] = True
        self._spectrum_acq = None
        threading.Thread(target=_run, daemon=True).start()

    def start_waveform_full(self, scope: str, channel: str, time_seconds: float,
                            name: str, save_root: str,
                            instrument_id: Optional[str] = None,
                            scope_conn=None,
                            results_callback: Optional[Callable[[dict], None]] = None,
                            progress_callback: Optional[Callable[[int, int], None]] = None,
                            error_callback: Optional[Callable[[str], None]] = None) -> None:
        """Run a waveform acquisition in a thread.

        ``scope`` is the SCPI dialect id (``"1"``/``"2"``/``"3"``).
        ``instrument_id`` is the actual VISA resource id
        (``"scope1"``/``"scope2"``/``"scope3"``); falls back to
        ``f"scope{scope}"`` when omitted.

        ``scope_conn`` is the live ``InstrumentConnection`` opened by
        the Connect tab. When provided the adapter reuses it via
        ``set_connection`` so we do not open a second VISA session on
        top of the one the Connect card is holding (which previously
        caused duplicate sessions and made the scope flaky, especially
        on Keysight). When ``None`` (legacy / test behaviour) the
        adapter opens its own connection.

        ``progress_callback`` is called once per captured segment as
        ``(index_1based, total_segments)`` so the GUI can print a
        progress line. Spectrum has the same plumbing.
        """
        from acquisition.waveform_acquisition import WaveformAcquisition

        if self.threads_active["waveform"]:
            msg = "Waveform measurement already in progress"
            self._dispatch_error(msg, error_callback)
            return

        actual_instrument_id = instrument_id or f"scope{scope}"

        def _on_progress(i: int, n: int) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(i, n)
                except Exception as e:
                    print(f"Error in waveform progress callback: {e}")
            if n > 0:
                pct = float(i) / float(n) * 100.0
                self._notify_gui("progress", pct)

        def _run():
            try:
                acq = WaveformAcquisition(scope_id=scope, channel=channel,
                                          instrument_id=actual_instrument_id,
                                          time_seconds=time_seconds,
                                          save_root=save_root, name=name,
                                          config=self.config.config)
                if scope_conn is not None:
                    acq.set_connection(scope_conn)
                self._waveform_acq = acq
                result = acq.run(progress_callback=_on_progress)
                payload = {
                    "path_d": result.path_d,
                    "time_base": result.time_base,
                    "num_points": result.num_points,
                    "y_data": result.y_data,
                    "x_data": result.x_data,
                    "zip_path": result.zip_path,
                }
                self.waveform_results = payload
                self._dispatch_result(payload, results_callback)
            except Exception as e:
                self._dispatch_error(f"Waveform measurement failed: {e}", error_callback)
            finally:
                self.threads_active["waveform"] = False
                self._waveform_acq = None

        self.threads_active["waveform"] = True
        self._waveform_acq = None
        threading.Thread(target=_run, daemon=True).start()

    def get_running_waveform(self):
        """Return the live ``WaveformAcquisition`` instance, or ``None``.

        Lets the GUI ask the worker to stop cooperatively without
        poking into facade internals.
        """
        acq = getattr(self, "_waveform_acq", None)
        if acq is None:
            return None
        if not self.threads_active.get("waveform", False):
            return None
        return acq

    # --- Persistence (delegates to acquisition.save) ---------------------

    def save_iv_results_to(self, name: str, path: str) -> None:
        from acquisition.save import save_iv_text
        if not getattr(self, "iv_results", None):
            self._notify_gui("error", "No IV results to save")
            return
        save_iv_text(path + name,
                     self.iv_results["voltage"],
                     self.iv_results["current"])
        self._notify_gui("data_ready", f"IV saved to {path}{name}.txt")

    def save_spectrum_results_to(self, name: str, path: str) -> None:
        from acquisition.save import save_spectrum_text
        if not getattr(self, "spectrum_results", None):
            self._notify_gui("error", "No spectrum results to save")
            return
        save_spectrum_text(path, name, self.spectrum_results["data"])
        self._notify_gui("data_ready", f"Spectrum saved to {path}{name}.txt")

    # --- Analysis helpers (thin pass-throughs to analysis/) ----------------

    def vbr_for(self, v_values, i_values) -> dict:
        from analysis.iv_analysis import calculate_vbr
        return calculate_vbr(v_values, i_values)

    def qr_for(self, v_values, i_values, v_range=None) -> dict:
        """Compute the quenching resistance.

        ``v_range`` is an optional ``(v_min, v_max)`` tuple that
        restricts the fit to a user-selected segment of the
        positive section. When ``None`` the legacy default
        (everything above 0.75 V) is used.
        """
        from analysis.iv_analysis import calculate_qr
        return calculate_qr(v_values, i_values, v_range=v_range)

    def plot_iv(self, ax, v_values, i_values, vbr_point=None, qr_line=None,
                dydx_over_y=None, v_for_ratio=None) -> None:
        from analysis.iv_analysis import plot_iv
        plot_iv(ax, v_values, i_values, vbr_point=vbr_point, qr_line=qr_line,
                dydx_over_y=dydx_over_y, v_for_ratio=v_for_ratio)

    def plot_vbr(self, ax, v_filtered, i_filtered, vbr_point,
                 dydx_over_y, v_for_ratio) -> None:
        """Draw the Vbr analysis: negative IV section plus the
        (dI/dV)/I derivative on a secondary y-axis. The Vbr
        point is marked with a red dot on both the IV curve
        and the derivative minimum."""
        from analysis.iv_analysis import plot_vbr
        plot_vbr(ax, v_filtered, i_filtered, vbr_point,
                 dydx_over_y, v_for_ratio)

    def plot_qr_initial(self, ax, v_positive, i_positive) -> None:
        """Draw the positive IV section with two pickable red
        markers at the curve endpoints. The GUI installs a
        PickEvent handler on those markers so the user can
        drag them along the curve and re-fit by pressing the
        Qr button again."""
        from analysis.iv_analysis import plot_qr_initial
        plot_qr_initial(ax, v_positive, i_positive)

    def plot_qr_with_fit(self, ax, v_positive, i_positive,
                         v_fit, i_fit) -> None:
        """Draw the positive IV section with the final QR fit
        line and its two endpoints highlighted in red."""
        from analysis.iv_analysis import plot_qr_with_fit
        plot_qr_with_fit(ax, v_positive, i_positive, v_fit, i_fit)

    def plot_complete(self, ax, v_values, i_values) -> None:
        """Draw the full IV curve (positive + negative sections)."""
        from analysis.iv_analysis import plot_complete
        plot_complete(ax, v_values, i_values)

    def find_histogram_peaks(self, data, bins: int = 50, prominence: float = 80) -> dict:
        from analysis.spectrum_analysis import find_histogram_peaks as _fhp
        return _fhp(data, bins=bins, prominence=prominence)

    def plot_histogram_with_peaks(self, ax, data, peaks_result=None) -> dict:
        from analysis.spectrum_analysis import plot_histogram_with_peaks as _phwp
        return _phwp(ax, data, peaks_result=peaks_result)

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

    # --- Lifecycle ---------------------------------------------------------

    def save_plot_as_png(self, figure, name: str, path: Optional[str] = None) -> None:
        """Save a matplotlib figure as PNG under the active output folder."""
        from pathlib import Path
        if path is None:
            output_dir = Path(self.config.get("paths", {}).get("output_dir", "data"))
        else:
            output_dir = Path(path)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{name}.png"
        figure.savefig(output_path, dpi=300, bbox_inches="tight")
        self._notify_gui("data_ready", f"Plot saved to {output_path}")

    def stop_all_measurements(self) -> None:
        """Signal all worker threads to stop and disconnect instruments."""
        for key in ("iv", "spectrum", "waveform"):
            self.threads_active[key] = False
        self._notify_gui("data_ready", "All measurements stopped")

    def get_running_spectrum(self):
        """Return the live ``SpectrumAcquisition`` instance, or ``None``.

        Lets the GUI ask the worker to stop cooperatively without
        poking into facade internals.
        """
        acq = getattr(self, "_spectrum_acq", None)
        if acq is None:
            return None
        if not self.threads_active.get("spectrum", False):
            return None
        return acq

    def cleanup(self) -> None:
        """Cleanup resources: stop measurements, disconnect instruments, drop
        any cached connections."""
        self.stop_all_measurements()

    # --- Internal helpers --------------------------------------------------

    def _dispatch_result(self, payload: dict,
                         callback: Optional[Callable[[dict], None]]) -> None:
        if callback is not None:
            try:
                callback(payload)
                return
            except Exception as e:
                print(f"Error in results callback: {e}")
        self._notify_gui("data_ready", payload)

    def _dispatch_error(self, msg: str,
                        callback: Optional[Callable[[str], None]]) -> None:
        if callback is not None:
            try:
                callback(msg)
                return
            except Exception as e:
                print(f"Error in error callback: {e}")
        self._notify_gui("error", msg)
