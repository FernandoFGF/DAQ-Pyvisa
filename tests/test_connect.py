"""
Tests for the Connect-tab machinery:

- config_loader.set_instrument_address updates the in-memory config
  and persists it to the YAML file on disk.
- acquisition.connection.identify runs *IDN? against a fake connection
  and returns the trimmed response.
- acquisition.connection.connect_and_identify returns (conn, idn) with
  the connection still open and the IDN string.
- gui.tabs.connect.DEFAULT_CARDS is a list of 4-tuples
  ``(id, name, description, dialect)`` and the Connected-panel
  iteration unpacks them with the 4-element shape.
- gui.tabs.connect.parse_idn_model returns the chunk between the
  first and second comma of a SCPI ``*IDN?`` response.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from config_loader import ConfigLoader
from tests.fake_connection import FakeConnection


class SetInstrumentAddressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.yaml"
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "instruments": {
                        "smu": {"name": "SMU", "address": "TCPIP::1.2.3.4::INSTR"},
                        "scope1": {"name": "RTA", "address": "TCPIP::5.6.7.8::INSTR"},
                    },
                    "paths": {"output_base": "Output"},
                },
                f,
            )
        # Reset the singleton state so load_config picks up our tmp file.
        ConfigLoader._instance = None
        ConfigLoader._loaded = False

    def tearDown(self) -> None:
        ConfigLoader._instance = None
        ConfigLoader._loaded = False
        self.tmp.cleanup()

    def test_set_in_memory_and_persists_to_disk(self):
        cfg = ConfigLoader()
        cfg.load_config(str(self.path))
        cfg.set_instrument_address("smu", "TCPIP::9.9.9.9::INSTR")

        # In-memory
        self.assertEqual(cfg.get_instrument_address("smu"), "TCPIP::9.9.9.9::INSTR")
        # On disk
        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["instruments"]["smu"]["address"], "TCPIP::9.9.9.9::INSTR")
        # Other instrument untouched
        self.assertEqual(data["instruments"]["scope1"]["address"], "TCPIP::5.6.7.8::INSTR")

    def test_set_unknown_instrument_raises(self):
        cfg = ConfigLoader()
        cfg.load_config(str(self.path))
        with self.assertRaises(KeyError):
            cfg.set_instrument_address("scope99", "TCPIP::1.1.1.1::INSTR")


class IdentifyTests(unittest.TestCase):
    def test_identify_with_provided_connection(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Rohde&Schwarz,RTA4004,1234,01.000\n")
        from acquisition.connection import identify
        result = identify("scope1", conn=fake)
        self.assertEqual(result, "Rohde&Schwarz,RTA4004,1234,01.000")
        self.assertIn("*IDN?", fake.queries)
        self.assertFalse(fake.closed)  # caller owns the connection

    def test_identify_opens_and_closes_when_no_conn(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Keysight,DSOX,ABC,01.00")

        with patch("acquisition.connection.open_pyvisa", return_value=fake) as open_mock:
            from acquisition.connection import identify
            result = identify("scope3")

        self.assertEqual(result, "Keysight,DSOX,ABC,01.00")
        open_mock.assert_called_once()
        self.assertTrue(fake.closed)

    def test_connect_and_identify_returns_open_connection(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Keysight,B2902A,MY-SMU,1.0")

        with patch("acquisition.connection.open_pyvisa", return_value=fake) as open_mock:
            from acquisition.connection import connect_and_identify
            conn, idn = connect_and_identify("smu")

        self.assertIs(conn, fake)
        self.assertEqual(idn, "Keysight,B2902A,MY-SMU,1.0")
        self.assertFalse(fake.closed)  # caller must close
        open_mock.assert_called_once()


class NormalizeAddressTests(unittest.TestCase):
    """Tests for gui_connect.normalize_address (pure function)."""

    def test_empty_inputs(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address(""), "")
        self.assertEqual(normalize_address(None), "")
        self.assertEqual(normalize_address("   "), "")

    def test_bare_ipv4_is_wrapped(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("192.168.0.32"),
                         "TCPIP::192.168.0.32::INSTR")
        self.assertEqual(normalize_address("169.254.168.151"),
                         "TCPIP::169.254.168.151::INSTR")
        self.assertEqual(normalize_address("  10.0.0.1  "),
                         "TCPIP::10.0.0.1::INSTR")

    def test_full_address_preserved(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("TCPIP::1.2.3.4::INSTR"),
                         "TCPIP::1.2.3.4::INSTR")
        self.assertEqual(normalize_address("USB0::0x1234::0x5678::INSTR"),
                         "USB0::0x1234::0x5678::INSTR")
        self.assertEqual(normalize_address("GPIB0::1::INSTR"),
                         "GPIB0::1::INSTR")

    def test_unknown_format_passes_through(self):
        """If the user typed something that doesn't look like an IPv4
        and doesn't contain '::', we don't touch it. Better to save
        whatever they meant than to corrupt it."""
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("ASRL1::INSTR"), "ASRL1::INSTR")
        # Even odd input is passed through unchanged.
        self.assertEqual(normalize_address("not-a-known-bus"), "not-a-known-bus")

    def test_custom_prefix_and_suffix(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("192.168.0.32",
                                          default_prefix="USB",
                                          default_suffix="MYDEV"),
                         "USB::192.168.0.32::MYDEV")


class DefaultCardsShapeTests(unittest.TestCase):
    """``DEFAULT_CARDS`` is iterated in ``_refresh_connected_list`` to
    decide the rendering order of the Connected panel. The iteration
    must unpack the 4-tuple shape
    ``(instrument_id, short_name, description, scope_dialect)``; a
    regression to a 3-element unpack used to silently fall back to
    the static card name and the user saw no model from ``*IDN?``."""

    def test_default_cards_are_4_tuples(self):
        from gui.tabs.connect import DEFAULT_CARDS
        for entry in DEFAULT_CARDS:
            self.assertEqual(
                len(entry), 4,
                f"DEFAULT_CARDS entry {entry!r} must have 4 elements, "
                f"got {len(entry)}"
            )
            instrument_id, short_name, description, dialect = entry
            self.assertTrue(instrument_id, "instrument_id must be non-empty")
            self.assertTrue(short_name, "short_name must be non-empty")
            self.assertTrue(description, "description must be non-empty")
            # dialect is None for non-scope instruments, otherwise a string.
            self.assertTrue(
                dialect is None or isinstance(dialect, str),
                f"dialect must be None or str, got {dialect!r}",
            )

    def test_4tuple_unpacking_does_not_raise(self):
        """Mirror the exact comprehension the Connected panel uses."""
        from gui.tabs.connect import DEFAULT_CARDS
        # If this comprehension raises, the panel falls back to a
        # lambda that returns "" for parse_idn_model and the user
        # never sees the model field of their *IDN? response.
        try:
            ordered_ids = [iid for iid, _, _, _ in DEFAULT_CARDS]
        except ValueError as e:
            self.fail(f"4-tuple unpacking raised: {e}")
        self.assertEqual(len(ordered_ids), len(DEFAULT_CARDS))
        self.assertIn("scope1", ordered_ids)
        self.assertIn("scope2", ordered_ids)
        self.assertIn("scope3", ordered_ids)


class ParseIdnModelTests(unittest.TestCase):
    """``parse_idn_model`` returns the chunk between the first and
    second comma of a ``*IDN?`` response (manufacturer, model, ...)."""

    def test_returns_model_field(self):
        from gui.tabs.connect import parse_idn_model
        self.assertEqual(parse_idn_model("Rohde&Schwarz,RTA4004,1234,01.00"),
                         "RTA4004")
        self.assertEqual(parse_idn_model("Keysight Technologies,DSOS054A,..."),
                         "DSOS054A")

    def test_empty_inputs(self):
        from gui.tabs.connect import parse_idn_model
        self.assertEqual(parse_idn_model(""), "")
        self.assertEqual(parse_idn_model("no_commas_here"), "")

    def test_strips_whitespace(self):
        from gui.tabs.connect import parse_idn_model
        self.assertEqual(parse_idn_model("Acme, Model-X ,sn,fw"), "Model-X")


if __name__ == "__main__":
    unittest.main()
