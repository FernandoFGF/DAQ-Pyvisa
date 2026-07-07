"""
Tests for the Connect-tab machinery:

- config_loader.set_instrument_address updates the in-memory config
  and persists it to the YAML file on disk.
- acquisition.connection.identify runs *IDN? against a fake connection
  and returns the trimmed response.
- acquisition.connection.connect_and_identify returns (conn, idn) with
  the connection still open and the IDN string.
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


if __name__ == "__main__":
    unittest.main()
