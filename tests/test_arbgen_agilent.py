"""
Tests for the Agilent / Keysight 33612A AWG dialect.

Mirrors the Siglent test in test_arbgen.py: each test injects
a ``FakeConnection`` and asserts the SCPI command sequence the
adapter sends matches the Agilent 33600A programming guide.
"""
from __future__ import annotations

import unittest

from acquisition.arbgen_acquisition import (
    AGILENT,
    apply_arbgen_params,
    reset_pulse_width_cache,
    set_arbgen_load,
    set_arbgen_output,
    set_arbgen_pulse_width,
)
from acquisition.arbgen_dialects import (
    SIGLENT,
    dialect_for_idn,
    wave_labels_for,
    wave_token_for,
)
from acquisition.arbgen_acquisition import detect_dialect
from tests.fake_connection import FakeConnection


class AgilentDialectDetectionTests(unittest.TestCase):
    def test_agilent_idn_resolves_to_agilent(self):
        idn = "Agilent Technologies,33612A,MY59602303,A.02.03-3.15-03-64-02"
        d = dialect_for_idn(idn)
        self.assertIs(d, AGILENT)

    def test_keysight_idn_resolves_to_agilent(self):
        # The 33600A rebranded to Keysight after 2014; same dialect.
        idn = "Keysight Technologies,33612A,MY59000001,01.00.0001"
        d = dialect_for_idn(idn)
        self.assertIs(d, AGILENT)

    def test_siglent_idn_resolves_to_siglent(self):
        idn = "Siglent Technologies,SDG2122X,SDG2XCAC6R0231,2.01.01.35R3B2"
        d = dialect_for_idn(idn)
        self.assertIs(d, SIGLENT)

    def test_unknown_idn_returns_none(self):
        self.assertIsNone(dialect_for_idn("Rohde & Schwarz,SMBV100A,1234,3.0"))

    def test_detect_dialect_against_fake(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Agilent Technologies,33612A,X,Y")
        self.assertIs(detect_dialect(fake), AGILENT)

    def test_detect_dialect_with_no_conn_returns_default(self):
        from acquisition.arbgen_acquisition import DEFAULT_DIALECT
        self.assertIs(detect_dialect(None), DEFAULT_DIALECT)


class AgilentWaveLabelsTests(unittest.TestCase):
    def test_wave_labels_for_agilent(self):
        labels = wave_labels_for(AGILENT)
        # The 33600A does not have a Triangle option; we omit it
        # from the dropdown for the Agilent dialect.
        self.assertNotIn("Triangle", labels)
        self.assertIn("Pulse train", labels)
        self.assertIn("Sine", labels)
        self.assertIn("Square", labels)

    def test_wave_token_for_agilent_pulse(self):
        self.assertEqual(wave_token_for(AGILENT, "Pulse train"), "PULS")

    def test_wave_token_for_agilent_sine(self):
        self.assertEqual(wave_token_for(AGILENT, "Sine"), "SIN")


class AgilentApplyParamsTests(unittest.TestCase):
    def test_apply_sends_sour1_commands(self):
        fake = FakeConnection()
        params = {
            "channel": "CH1",
            "waveform_label": "Pulse train",
            "frequency_hz": "5000",
            "amplitude_vpp": "2.0",
            "impedance": "HiZ",
            "offset_v": "0.1",
            "phase_deg": "0",
            "width_s": "1e-5",
        }
        apply_arbgen_params(params, conn=fake, dialect=AGILENT)
        # FUNC first
        self.assertIn("SOUR1:FUNC PULS", fake.writes)
        self.assertIn("SOUR1:FREQ 5000.0", fake.writes)
        self.assertIn("SOUR1:VOLT 2.0", fake.writes)
        self.assertIn("SOUR1:VOLT:OFFS 0.1", fake.writes)
        self.assertIn("SOUR1:PHAS 0.0", fake.writes)
        # Pulse width is sent because the wave is PULS.
        self.assertIn("SOUR1:FUNC:PULS:WIDT 1.000E-05", fake.writes)
        # Output + load are NOT sent by apply_arbgen_params.
        for w in fake.writes:
            self.assertFalse(w.startswith("OUTP1"), f"unexpected OUTP line: {w!r}")

    def test_apply_omits_pulse_width_for_non_pulse(self):
        fake = FakeConnection()
        params = {
            "channel": "CH1",
            "waveform_label": "Sine",
            "frequency_hz": "1000",
            "amplitude_vpp": "1.0",
            "impedance": "HiZ",
            "offset_v": "0",
            "phase_deg": "0",
            "width_s": "1e-5",
        }
        apply_arbgen_params(params, conn=fake, dialect=AGILENT)
        # FUNC + freq/amp/offset/phase only, no PULS:WIDT.
        self.assertIn("SOUR1:FUNC SIN", fake.writes)
        self.assertNotIn(
            "SOUR1:FUNC:PULS:WIDT 1.000E-05", fake.writes,
        )

    def test_apply_uses_sour2_for_ch2(self):
        fake = FakeConnection()
        params = {
            "channel": "CH2",
            "waveform_label": "Sine",
            "frequency_hz": "1000",
            "amplitude_vpp": "1.0",
            "impedance": "HiZ",
            "offset_v": "0",
            "phase_deg": "0",
            "width_s": "1e-5",
        }
        apply_arbgen_params(params, conn=fake, dialect=AGILENT)
        self.assertIn("SOUR2:FUNC SIN", fake.writes)
        self.assertIn("SOUR2:FREQ 1000.0", fake.writes)


class AgilentOutputAndLoadTests(unittest.TestCase):
    def test_output_on_ch1(self):
        fake = FakeConnection()
        set_arbgen_output("CH1", True, conn=fake, dialect=AGILENT)
        self.assertEqual(fake.writes, ["OUTP1 ON"])

    def test_output_off_ch2(self):
        fake = FakeConnection()
        set_arbgen_output("CH2", False, conn=fake, dialect=AGILENT)
        self.assertEqual(fake.writes, ["OUTP2 OFF"])

    def test_load_50_ch1(self):
        fake = FakeConnection()
        set_arbgen_load("CH1", "50 Ohm", conn=fake, dialect=AGILENT)
        self.assertEqual(fake.writes, ["OUTP1:LOAD 50"])

    def test_load_hiz_ch2(self):
        fake = FakeConnection()
        set_arbgen_load("CH2", "HiZ", conn=fake, dialect=AGILENT)
        self.assertEqual(fake.writes, ["OUTP2:LOAD INF"])


class AgilentPulseWidthTests(unittest.TestCase):
    def setUp(self):
        reset_pulse_width_cache()

    def test_pulse_width_ch1(self):
        fake = FakeConnection()
        set_arbgen_pulse_width("CH1", 1.5e-5, conn=fake, dialect=AGILENT)
        self.assertEqual(fake.writes, ["SOUR1:FUNC:PULS:WIDT 1.500E-05"])

    def test_pulse_width_dedup(self):
        """Two focus-out events with the same value should send only one command."""
        reset_pulse_width_cache()
        fake = FakeConnection()
        set_arbgen_pulse_width("CH1", 1.5e-5, conn=fake, dialect=AGILENT)
        set_arbgen_pulse_width("CH1", 1.5e-5, conn=fake, dialect=AGILENT)
        self.assertEqual(fake.writes, ["SOUR1:FUNC:PULS:WIDT 1.500E-05"])


class SiglentRegressionTests(unittest.TestCase):
    """Quick sanity that the legacy Siglent dialect still works
    after the refactor: same command shape as the original."""

    def test_apply_siglent_sends_bswv_lines(self):
        fake = FakeConnection()
        params = {
            "channel": "CH1",
            "waveform_label": "Sine",
            "frequency_hz": "1000",
            "amplitude_vpp": "1.0",
            "impedance": "HiZ",
            "offset_v": "0",
            "phase_deg": "0",
            "width_s": "1e-6",
        }
        apply_arbgen_params(params, conn=fake, dialect=SIGLENT)
        self.assertIn("C1:BSWV WVTP,SINE", fake.writes)
        self.assertIn("C1:BSWV FRQ,1000.0", fake.writes)
        self.assertIn("C1:BSWV WIDTH,1.000E-06", fake.writes)

    def test_siglent_load_hiz(self):
        fake = FakeConnection()
        set_arbgen_load("CH1", "HiZ", conn=fake, dialect=SIGLENT)
        self.assertEqual(fake.writes, ["C1:OUTP LOAD,HZ"])

    def test_siglent_output_on(self):
        fake = FakeConnection()
        set_arbgen_output("CH1", True, conn=fake, dialect=SIGLENT)
        self.assertEqual(fake.writes, ["C1:OUTP ON"])


if __name__ == "__main__":
    unittest.main()
