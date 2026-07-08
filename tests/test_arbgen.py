"""
Tests for the ArbGen UI scaffold and the SCPI stubs.

The Siglent SDG2122X is the first AWG we are targeting. The
SCPI commands are still being finalised with the user, so the
adapter is a stub that prints the command it would send. These
tests lock the parameter shape and the on/off state machine.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import customtkinter as ctk

from gui.tabs import arbgen as arbgen_tab
from gui.tabs.arbgen import (
    WAVEFORM_BY_LABEL,
    WAVEFORM_LABELS,
)
from acquisition import arbgen_acquisition as arbgen_acq
from acquisition.arbgen_acquisition import (
    apply_arbgen_params,
    set_arbgen_output,
)


class WaveformOptionsTests(unittest.TestCase):
    def test_waveform_options_contain_required_types(self):
        for required in ("Sine", "Square", "Triangle", "Pulse train"):
            self.assertIn(required, WAVEFORM_LABELS,
                          f"missing wave type {required!r}")

    def test_triangle_maps_to_ramp_scpi(self):
        # The Siglent uses RAMP for triangle waveforms.
        self.assertEqual(WAVEFORM_BY_LABEL["Triangle"], "RAMP")

    def test_pulse_train_maps_to_pulse_scpi(self):
        self.assertEqual(WAVEFORM_BY_LABEL["Pulse train"], "PULSE")


class ApplyArbgenParamsStubTests(unittest.TestCase):
    """The stub ``apply_arbgen_params`` and ``set_arbgen_output``
    print the SCPI command they would send. We just assert the
    output contains the parameter summary so we can replace
    the stub with real pyvisa calls without breaking the
    contract."""

    def setUp(self) -> None:
        self.params = {
            "channel": "CH1",
            "waveform_label": "Sine",
            "waveform_scpi": "SINE",
            "frequency_hz": "1000",
            "amplitude_vpp": "1.0",
            "impedance": "HiZ",
            "offset_v": "0.0",
            "phase_deg": "0",
        }

    def test_apply_prints_scpi_summary(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            apply_arbgen_params(self.params)
        out = buf.getvalue()
        self.assertIn("SCPI(apply)", out)
        self.assertIn("channel=CH1", out)
        self.assertIn("wave=SINE", out)
        self.assertIn("freq=1000Hz", out)
        self.assertIn("amp=1.0Vpp", out)
        self.assertIn("Z=HiZ", out)

    def test_set_output_on(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            set_arbgen_output("CH1", True)
        out = buf.getvalue()
        self.assertIn("SCPI(output)", out)
        self.assertIn("channel=CH1", out)
        self.assertIn("state=ON", out)

    def test_set_output_off(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            set_arbgen_output("CH2", False)
        out = buf.getvalue()
        self.assertIn("channel=CH2", out)
        self.assertIn("state=OFF", out)

    def test_format_params_summary_round_trip(self):
        # Every value surfaced by the GUI must show up in the
        # summary so a human can read the terminal output and
        # know exactly what the user just configured.
        summary = arbgen_acq._format_params_summary(self.params)
        # The summary uses short labels (channel=, wave=, freq=, ...).
        for label_value in (
            "CH1", "SINE", "1000Hz", "1.0Vpp", "HiZ", "0.0V", "0deg",
        ):
            self.assertIn(label_value, summary)


class _StubTabView:
    """Minimal stand-in for ``customtkinter.CTkTabview`` so we
    can build the ArbGen tab inside a plain Tk root without
    standing up the full App. Each tab is just a
    ``CTkFrame`` parented to the test root."""

    def __init__(self, root):
        self._tab_dict = {}
        self._root = root

    def add(self, name):
        self._tab_dict[name] = ctk.CTkFrame(self._root)

    def tab(self, name):
        return self._tab_dict[name]


def _build_stub(root):
    class _Stub:
        pass

    stub = _Stub()
    stub.tabview = _StubTabView(root)
    # Provide a minimal config so the handler does not blow up
    # before the (mocked) adapter call lands. The mocked
    # adapter does not actually touch config.config.
    stub.config = type("Cfg", (), {"config": None})()
    return stub


class SettingArbgenSmokeTest(unittest.TestCase):
    """Build the tab in a Tk root and assert the key widgets
    exist on ``self``. Catches regressions where a control
    is renamed or removed."""

    def test_setting_arbgen_creates_controls(self):
        try:
            root = ctk.CTk()
        except Exception as e:
            self.skipTest(f"CTk unavailable: {e}")

        stub = _build_stub(root)
        try:
            arbgen_tab.setting_arbgen(stub)
            for attr in (
                "arbgen_channel",
                "arbgen_waveform",
                "arbgen_freq",
                "arbgen_amp",
                "arbgen_offset",
                "arbgen_phase",
                "arbgen_impedance",
                "arbgen_output",
                "arbgen_update_button",
            ):
                self.assertTrue(hasattr(stub, attr),
                                f"setting_arbgen did not set {attr!r}")
            # On/Off switch defaults to OFF.
            self.assertEqual(stub.arbgen_output.get(), "OFF")
            # Channel defaults to CH1.
            self.assertEqual(stub.arbgen_channel.get(), "CH1")
            # Impedance defaults to HiZ.
            self.assertEqual(stub.arbgen_impedance.get(), "HiZ")
            # Wave type defaults to Sine.
            self.assertEqual(stub.arbgen_waveform.get(), "Sine")
        finally:
            root.destroy()


class ArbgenActionHandlersTests(unittest.TestCase):
    """The GUI-side ``arbgen_update`` and ``arbgen_toggle_output``
    are the only entry points from the buttons. They must
    print a structured line and delegate to the adapter.
    """

    def setUp(self) -> None:
        try:
            self.root = ctk.CTk()
        except Exception as e:
            self.skipTest(f"CTk unavailable: {e}")

        self.stub = _build_stub(self.root)
        arbgen_tab.setting_arbgen(self.stub)

    def tearDown(self) -> None:
        self.root.destroy()

    def test_arbgen_update_prints_summary(self):
        # Inject user-typed values into the entries. Without
        # this the CTkEntry widgets are empty and the summary
        # would only contain the channel and wave type.
        self.stub.arbgen_freq.insert(0, "1000")
        self.stub.arbgen_amp.insert(0, "1.0")
        self.stub.arbgen_offset.insert(0, "0.0")
        self.stub.arbgen_phase.insert(0, "0")
        # The GUI imports the adapter functions at module
        # load time, so we patch them in gui.tabs.arbgen where
        # they are now bound.
        with patch("gui.tabs.arbgen.apply_arbgen_params") as mock_apply:
            buf = io.StringIO()
            with redirect_stdout(buf):
                arbgen_tab.arbgen_update(self.stub)
            mock_apply.assert_called_once()
        out = buf.getvalue()
        self.assertIn("[ArbGen] Update", out)
        self.assertIn("CH1", out)
        self.assertIn("SINE", out)
        self.assertIn("1000", out)

    def test_arbgen_toggle_output_prints_state(self):
        with patch("gui.tabs.arbgen.set_arbgen_output") as mock_set:
            buf = io.StringIO()
            with redirect_stdout(buf):
                arbgen_tab.arbgen_toggle_output(self.stub, "ON")
                arbgen_tab.arbgen_toggle_output(self.stub, "OFF")
            self.assertEqual(mock_set.call_count, 2)
        out = buf.getvalue()
        self.assertIn("Output ON", out)
        self.assertIn("Output OFF", out)


if __name__ == "__main__":
    unittest.main()
