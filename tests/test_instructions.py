"""
Tests for gui/instructions.py — per-scope, per-function
instructions loaded from instructions.json.
"""

from __future__ import annotations

import unittest

from gui.instructions import load_instructions


class LoadInstructionsTests(unittest.TestCase):
    def test_happy_path_spectrum_rta(self):
        lines = load_instructions("Spectrum", "RTA")
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)
        self.assertNotEqual(lines, ["none"])
        # The seeded first line is the header.
        self.assertIn("Spectrum", lines[0])
        self.assertIn("RTA", lines[0])

    def test_happy_path_waveform_keysight(self):
        lines = load_instructions("Waveform", "KEY")
        self.assertGreater(len(lines), 0)
        self.assertIn("Keysight", lines[0])

    def test_unknown_function_returns_none(self):
        self.assertEqual(load_instructions("BogusTab", "RTA"), ["none"])

    def test_unknown_scope_returns_none(self):
        # Function exists but scope is unknown.
        self.assertEqual(load_instructions("Spectrum", "Noscope"), ["none"])

    def test_known_function_unknown_scope_falls_back_to_none(self):
        # Empty branch in the JSON (e.g. iv/rta is currently ["none"]).
        self.assertEqual(load_instructions("IV Curves", "RTA"), ["none"])

    def test_friendly_names_normalised(self):
        # The friendly names from the GUI must map to the right JSON
        # entry. ``RTA``/``RTO``/``KEY`` are the values shown on the
        # Connect cards and on the spectrum/waveform scope label.
        a = load_instructions("Spectrum", "RTA")
        b = load_instructions("Spectrum", "RTO")
        c = load_instructions("Spectrum", "KEY")
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, c)
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()
