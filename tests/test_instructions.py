"""
Tests for gui/instructions.py — per-scope, per-function
instructions loaded from instructions.json.
"""

from __future__ import annotations

import os
import unittest

from gui.instructions import load_instructions


class LoadInstructionsTests(unittest.TestCase):
    def test_spectrum_rta_returns_seeded_content(self):
        """The RTA spectrum block is non-empty and not the literal
        ``["none"]`` fallback (the user fills this with their own
        RTA-specific instructions)."""
        lines = load_instructions("Spectrum", "RTA")
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)
        self.assertNotEqual(lines, ["none"])

    def test_spectrum_keysight_returns_seeded_content(self):
        lines = load_instructions("Spectrum", "KEY")
        self.assertGreater(len(lines), 0)
        self.assertNotEqual(lines, ["none"])
        joined = " ".join(lines).lower()
        self.assertIn("keysight", joined)

    def test_waveform_keysight_returns_seeded_content(self):
        lines = load_instructions("Waveform", "KEY")
        self.assertGreater(len(lines), 0)
        self.assertNotEqual(lines, ["none"])
        joined = " ".join(lines).lower()
        self.assertIn("keysight", joined)

    def test_unknown_function_returns_none(self):
        self.assertEqual(load_instructions("BogusTab", "RTA"), ["none"])

    def test_unknown_scope_returns_none(self):
        # Function exists but scope is unknown.
        self.assertEqual(load_instructions("Spectrum", "Noscope"), ["none"])

    def test_known_function_unknown_scope_falls_back_to_none(self):
        # Empty branch in the JSON (e.g. iv/rta is currently ["none"]).
        self.assertEqual(load_instructions("IV Curves", "RTA"), ["none"])

    def test_friendly_names_normalised(self):
        """The friendly names from the GUI must map to the right JSON
        entry. ``RTA``/``RTO``/``KEY`` are the values shown on the
        Connect cards and on the spectrum/waveform scope label."""
        a = load_instructions("Spectrum", "RTA")
        b = load_instructions("Spectrum", "RTO")
        c = load_instructions("Spectrum", "KEY")
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, c)
        self.assertNotEqual(a, c)

    def test_iv_section_falls_back_to_none(self):
        # The IV section in instructions.json is currently all
        # ``["none"]`` placeholders (no scope-specific IV docs yet).
        for scope in ("RTA", "RTO", "KEY"):
            with self.subTest(scope=scope):
                self.assertEqual(load_instructions("IV Curves", scope), ["none"])


class InstructionsFileTests(unittest.TestCase):
    """Sanity check: instructions.json exists at the project root
    and is a valid JSON document with the expected top-level keys."""

    def test_instructions_json_exists(self):
        from gui.instructions import _project_root
        path = os.path.join(_project_root(), "instructions.json")
        self.assertTrue(os.path.isfile(path), f"missing {path}")

    def test_instructions_json_has_expected_keys(self):
        from gui.instructions import _load_raw
        data = _load_raw()
        self.assertNotEqual(data, {}, "instructions.json is empty or malformed")
        for key in ("spectrum", "waveform", "iv"):
            self.assertIn(key, data, f"missing top-level key {key!r}")


if __name__ == "__main__":
    unittest.main()
