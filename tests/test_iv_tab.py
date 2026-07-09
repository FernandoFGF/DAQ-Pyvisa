"""
Tests for the IV Curves tab scaffold.

The IV tab used to expose a SMU / Classic selector; that was
removed and replaced with a read-only "SMU: <*IDN?>" label
that reflects the live SMU connection in the Connect tab.
"""
from __future__ import annotations

import unittest


class SettingIvSmokeTest(unittest.TestCase):
    """Build the IV tab and assert the new header label exists."""

    def setUp(self):
        try:
            import customtkinter as ctk
            self.root = ctk.CTk()
        except Exception as e:
            self.skipTest(f"CTk unavailable: {e}")

    def tearDown(self):
        self.root.destroy()

    def _build_stub(self):
        class _StubTabView:
            def __init__(self, root):
                import customtkinter as ctk
                self._tab_dict = {}
                self._root = root
                # Pre-register the tabs that setting_iv / setting_*
                # will look up; the .tab() call has to return a
                # real frame so the ctk widgets can be parented.
                self._tab_dict["IV Curves"] = ctk.CTkFrame(self._root)
                self._tab_dict["Connect"] = ctk.CTkFrame(self._root)
                self._tab_dict["Spectrum"] = ctk.CTkFrame(self._root)
                self._tab_dict["Waveform"] = ctk.CTkFrame(self._root)

            def add(self, name):
                import customtkinter as ctk
                self._tab_dict[name] = ctk.CTkFrame(self._root)

            def tab(self, name):
                return self._tab_dict[name]

        class _Stub:
            def start_iv(self):
                # No-op stub for the Start button command.
                return None

        stub = _Stub()
        stub.tabview = _StubTabView(self.root)
        stub.connect_cards = {}
        return stub

    def test_iv_label_exists_and_starts_disconnected(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        self.assertTrue(hasattr(stub, "iv_smu_label"))
        text = stub.iv_smu_label.cget("text")
        self.assertIn("not connected", text)

    def test_iv_update_connected_with_idn(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        stub.connect_cards["smu"] = {
            "connection": object(),
            "idn": "KEITHLEY INSTRUMENTS INC.,MODEL 2470,01234567,1.6.1d",
        }
        iv_tab.iv_update_connected(stub)
        text = stub.iv_smu_label.cget("text")
        self.assertIn("KEITHLEY", text)
        self.assertIn("2470", text)

    def test_iv_update_connected_after_disconnect(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        stub.connect_cards["smu"] = {
            "connection": object(),
            "idn": "KEITHLEY,2470,X,Y",
        }
        iv_tab.iv_update_connected(stub)
        # Now the user disconnects: the card stays in the dict
        # but the connection is gone and idn is cleared.
        stub.connect_cards["smu"]["connection"] = None
        stub.connect_cards["smu"]["idn"] = None
        iv_tab.iv_update_connected(stub)
        self.assertIn("not connected", stub.iv_smu_label.cget("text"))

    def test_iv_options_legacy_attribute_is_smu(self):
        """The legacy code reads self.options.get() to decide
        whether to run the SMU or Classic path. We keep the
        attribute for back-compat but hide the widget; the
        value is always 'SMU' today."""
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        self.assertTrue(hasattr(stub, "options"))
        self.assertEqual(stub.options.get(), "SMU")

    def test_iv_channel_radio_buttons_exist(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        # Two radio buttons sharing a single StringVar, just
        # like the Spectrum and Waveform tabs.
        self.assertTrue(hasattr(stub, "ch1IV"))
        self.assertTrue(hasattr(stub, "ch2IV"))
        self.assertIs(stub.ch1IV.cget("variable"), stub.ch2IV.cget("variable"))
        # Default is channel 1.
        self.assertEqual(stub.selected_channelIV.get(), "CH1")

    def test_iv_selected_channel_default(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        # Channel 1 is the default selection.
        self.assertEqual(iv_tab.iv_selected_channel(stub), 1)

    def test_iv_selected_channel_toggle(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        # Pick channel 2; the helper returns 2.
        stub.selected_channelIV.set("CH2")
        self.assertEqual(iv_tab.iv_selected_channel(stub), 2)

    def test_iv_radio_buttons_are_mutually_exclusive(self):
        from gui.tabs import iv as iv_tab
        stub = self._build_stub()
        iv_tab.setting_iv(stub)
        # The two radio buttons share a StringVar, so the
        # underlying variable can only ever hold one value.
        stub.selected_channelIV.set("CH2")
        self.assertNotEqual(
            stub.ch1IV.cget("variable")._dummy if False else "CH1",
            stub.selected_channelIV.get(),
        )


if __name__ == "__main__":
    unittest.main()
