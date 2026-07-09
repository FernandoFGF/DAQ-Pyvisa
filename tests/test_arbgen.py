"""
Tests for the ArbGen UI scaffold and the Siglent SDG2122X SCPI
adapter.

The Siglent commands sent to the scope are part of the contract
the user agreed on, so the adapter is tested end-to-end: a
parameter dict in, a list of SCPI writes out, with each write
matching one of the documented commands.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import customtkinter as ctk

from gui.tabs import arbgen as arbgen_tab
from gui.tabs.arbgen import (
    DEFAULT_CONNECTED_LABEL,
)
from acquisition import arbgen_acquisition as arbgen_acq
from acquisition.arbgen_acquisition import (
    SIGLENT,
    apply_arbgen_params,
    set_arbgen_load,
    set_arbgen_output,
    set_arbgen_pulse_width,
    wave_labels_for,
    wave_token_for,
)
from tests.fake_connection import FakeConnection


# Backwards-compat shim for the old module-level constants: the
# Siglent dialect is the default, so the dropdown labels are
# exactly the Siglent wave list.
WAVEFORM_LABELS = wave_labels_for(SIGLENT)
WAVEFORM_BY_LABEL = {label: wave_token_for(SIGLENT, label) for label in WAVEFORM_LABELS}


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


class SiglentScpiCommandTests(unittest.TestCase):
    """Lock the SCPI command strings the adapter issues.

    These tests use the FakeConnection to capture the writes
    and assert the exact SCPI tokens. The user reviewed and
    approved these commands; if you change one here you must
    also change the documented table.
    """

    def setUp(self) -> None:
        self.params = {
            "channel": "CH1",
            "waveform_label": "Sine",
            "waveform_scpi": "SINE",
            "frequency_hz": "1000",
            "amplitude_vpp": "2.0",
            "impedance": "HiZ",
            "offset_v": "0.5",
            "phase_deg": "90",
            "width_s": "10E-6",
        }

    def test_apply_emits_full_parameter_batch(self):
        conn = FakeConnection()
        apply_arbgen_params(self.params, conn=conn)
        expected = [
            "C1:BSWV WVTP,SINE",
            "C1:BSWV FRQ,1000.0",
            "C1:BSWV AMP,2.0",
            "C1:BSWV OFST,0.5",
            "C1:BSWV PHSE,90.0",
            "C1:BSWV WIDTH,1.000E-05",
        ]
        self.assertEqual(conn.writes, expected)

    def test_apply_ch2_uses_c2_prefix(self):
        conn = FakeConnection()
        params = dict(self.params, channel="CH2")
        apply_arbgen_params(params, conn=conn)
        self.assertTrue(all(w.startswith("C2:") for w in conn.writes),
                        f"expected C2 prefix, got {conn.writes}")

    def test_apply_handles_missing_or_bad_values(self):
        conn = FakeConnection()
        # Empty / non-numeric strings fall back to safe defaults.
        params = {
            "channel": "CH1",
            "waveform_scpi": "SINE",
            "frequency_hz": "",
            "amplitude_vpp": "abc",
            "offset_v": None,
            "phase_deg": "0",
            "width_s": "?",
        }
        apply_arbgen_params(params, conn=conn)
        # Defaults: freq=1000, amp=1, offset=0, phase=0, width=1us.
        joined = " | ".join(conn.writes)
        self.assertIn("FRQ,1000.0", joined)
        self.assertIn("AMP,1.0", joined)
        self.assertIn("OFST,0.0", joined)
        self.assertIn("PHSE,0.0", joined)

    def test_set_output_on(self):
        conn = FakeConnection()
        set_arbgen_output("CH1", True, conn=conn)
        self.assertEqual(conn.writes, ["C1:OUTP ON"])

    def test_set_output_off(self):
        conn = FakeConnection()
        set_arbgen_output("CH2", False, conn=conn)
        self.assertEqual(conn.writes, ["C2:OUTP OFF"])

    def test_set_load_50_ohm(self):
        conn = FakeConnection()
        set_arbgen_load("CH1", "50 Ohm", conn=conn)
        self.assertEqual(conn.writes, ["C1:OUTP LOAD,50"])

    def test_set_load_hiz(self):
        conn = FakeConnection()
        set_arbgen_load("CH2", "HiZ", conn=conn)
        self.assertEqual(conn.writes, ["C2:OUTP LOAD,HZ"])

    def test_set_pulse_width(self):
        conn = FakeConnection()
        set_arbgen_pulse_width("CH1", 1.5e-6, conn=conn)
        self.assertEqual(conn.writes, ["C1:BSWV WIDTH,1.500E-06"])


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
    # No live AWG connection by default; the GUI just prints
    # the SCPI line. Tests that need a live conn set this
    # attribute explicitly.
    stub.connect_cards = {}
    return stub


class SettingArbgenSmokeTest(unittest.TestCase):
    """Build the tab in a Tk root and assert the key widgets
    exist on ``self``. Catches regressions where a control
    is renamed or removed."""

    def test_setting_arbgen_creates_per_channel_panels(self):
        try:
            root = ctk.CTk()
        except Exception as e:
            self.skipTest(f"CTk unavailable: {e}")

        stub = _build_stub(root)
        try:
            arbgen_tab.setting_arbgen(stub)
            # Connected indicator exists and names the Siglent.
            self.assertTrue(hasattr(stub, "arbgen_connected_label"))
            self.assertIn("Siglent", stub.arbgen_connected_label.cget("text"))
            self.assertIn(DEFAULT_CONNECTED_LABEL,
                          stub.arbgen_connected_label.cget("text"))
            # The new shape: a dict keyed by channel.
            self.assertTrue(hasattr(stub, "arbgen_panels"))
            self.assertEqual(set(stub.arbgen_panels.keys()),
                             {"CH1", "CH2"})
            for ch in ("CH1", "CH2"):
                panel = stub.arbgen_panels[ch]
                for attr in ("waveform", "freq", "amp", "offset",
                             "phase", "width", "impedance", "output",
                             "update_button"):
                    self.assertIn(attr, panel,
                                  f"CH{ch} panel missing {attr!r}")
                # On/Off defaults to OFF.
                self.assertEqual(panel["output"].get(), "OFF")
                # Impedance defaults to HiZ.
                self.assertEqual(panel["impedance"].get(), "HiZ")
                # Wave type defaults to Sine.
                self.assertEqual(panel["waveform"].get(), "Sine")
        finally:
            root.destroy()


class ArbgenActionHandlersTests(unittest.TestCase):
    """The GUI-side ``arbgen_update`` and ``arbgen_toggle_output``
    are the only entry points from the buttons. They must
    print a structured line and delegate to the adapter."""

    def setUp(self) -> None:
        try:
            self.root = ctk.CTk()
        except Exception as e:
            self.skipTest(f"CTk unavailable: {e}")

        self.stub = _build_stub(self.root)
        arbgen_tab.setting_arbgen(self.stub)

    def tearDown(self) -> None:
        self.root.destroy()

    def _fill(self, ch: str) -> None:
        panel = self.stub.arbgen_panels[ch]
        panel["freq"].insert(0, "1000")
        panel["amp"].insert(0, "1.0")
        panel["offset"].insert(0, "0.0")
        panel["phase"].insert(0, "0")
        panel["width"].insert(0, "10E-6")

    def test_arbgen_update_ch1_prints_summary(self):
        self._fill("CH1")
        with patch("gui.tabs.arbgen.apply_arbgen_params") as mock_apply:
            buf = io.StringIO()
            with redirect_stdout(buf):
                arbgen_tab.arbgen_update(self.stub, "CH1")
            mock_apply.assert_called_once()
        out = buf.getvalue()
        self.assertIn("[ArbGen] Update", out)
        self.assertIn("CH1", out)
        self.assertIn("SINE", out)
        self.assertIn("1000", out)
        self.assertIn("10E-6", out)

    def test_arbgen_update_ch2_isolated_from_ch1(self):
        # Edit CH1 only; pressing CH2's Update should still
        # show CH1's empty values.
        self._fill("CH1")
        with patch("gui.tabs.arbgen.apply_arbgen_params") as mock_apply:
            buf = io.StringIO()
            with redirect_stdout(buf):
                arbgen_tab.arbgen_update(self.stub, "CH2")
            mock_apply.assert_called_once()
        out = buf.getvalue()
        # CH2's freq entry was never typed into, so the
        # summary should not contain "1000" for the CH2 call.
        self.assertIn("CH2", out)
        self.assertNotIn("freq=1000Hz", out)

    def test_arbgen_toggle_output_per_channel(self):
        with patch("gui.tabs.arbgen.set_arbgen_output") as mock_set:
            buf = io.StringIO()
            with redirect_stdout(buf):
                arbgen_tab.arbgen_toggle_output(self.stub, "CH1", "ON")
                arbgen_tab.arbgen_toggle_output(self.stub, "CH2", "OFF")
            self.assertEqual(mock_set.call_count, 2)
        out = buf.getvalue()
        self.assertIn("Output ON on CH1", out)
        self.assertIn("Output OFF on CH2", out)

    def test_arbgen_toggle_uses_live_connection_from_connect_cards(self):
        """The GUI on/off switch must hand the adapter the
        live pyvisa connection that the Connect tab opened
        in self.connect_cards['arbGen']['connection']. The
        previous code opened no connection, so the SCPI
        line was only printed, never sent to the scope."""
        from tests.fake_connection import FakeConnection
        live = FakeConnection()
        self.stub.connect_cards["arbGen"] = {
            "connection": live, "idn": "...",
        }
        with patch("gui.tabs.arbgen.set_arbgen_output") as mock_set:
            arbgen_tab.arbgen_toggle_output(self.stub, "CH1", "ON")
            mock_set.assert_called_once()
        # The live connection was passed in as the ``conn``
        # keyword argument; the adapter would have called
        # .write on it to issue the SCPI command.
        kwargs = mock_set.call_args.kwargs
        self.assertIs(kwargs["conn"], live)

    def test_arbgen_update_uses_live_connection_from_connect_cards(self):
        from tests.fake_connection import FakeConnection
        live = FakeConnection()
        self.stub.connect_cards["arbGen"] = {
            "connection": live, "idn": "...",
        }
        self.stub.arbgen_panels["CH1"]["freq"].insert(0, "1000")
        with patch("gui.tabs.arbgen.apply_arbgen_params") as mock_apply:
            arbgen_tab.arbgen_update(self.stub, "CH1")
            mock_apply.assert_called_once()
        kwargs = mock_apply.call_args.kwargs
        self.assertIs(kwargs["conn"], live)

    def test_arbgen_handles_missing_connect_cards(self):
        """If the AWG was never connected, the GUI still works
        and just prints the SCPI line (no exception)."""
        self.stub.connect_cards = {}
        with patch("gui.tabs.arbgen.set_arbgen_output") as mock_set:
            buf = io.StringIO()
            with redirect_stdout(buf):
                arbgen_tab.arbgen_toggle_output(self.stub, "CH1", "ON")
            mock_set.assert_called_once()
        # The adapter was called with conn=None.
        self.assertIsNone(mock_set.call_args.kwargs["conn"])

    def test_arbgen_change_load_delegates_to_adapter(self):
        with patch("gui.tabs.arbgen.set_arbgen_load") as mock_set:
            arbgen_tab.arbgen_change_load(self.stub, "CH1", "50 Ohm")
            mock_set.assert_called_once()
            # The adapter is invoked with kwargs only.
            kwargs = mock_set.call_args.kwargs
            self.assertEqual(kwargs["channel"], "CH1")
            self.assertEqual(kwargs["impedance"], "50 Ohm")

    def test_arbgen_change_width_validates_input(self):
        with patch("gui.tabs.arbgen.set_arbgen_pulse_width") as mock_set:
            # Bad width: ignored.
            self.stub.arbgen_panels["CH1"]["width"].insert(0, "abc")
            arbgen_tab.arbgen_change_width(self.stub, "CH1")
            mock_set.assert_not_called()

            # Good width: forwarded.
            self.stub.arbgen_panels["CH1"]["width"].delete(0, "end")
            self.stub.arbgen_panels["CH1"]["width"].insert(0, "1.5E-6")
            arbgen_tab.arbgen_change_width(self.stub, "CH1")
            mock_set.assert_called_once()
            self.assertAlmostEqual(mock_set.call_args.kwargs["width_s"],
                                    1.5e-6, places=12)


if __name__ == "__main__":
    unittest.main()
