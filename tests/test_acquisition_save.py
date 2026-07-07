"""
Tests for the pure save helpers in acquisition/save.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from acquisition.save import (
    create_zip,
    ensure_dir,
    remove_path,
    save_iv_text,
    save_spectrum_text,
    write_waveform_file,
    write_waveform_metadata,
)


class EnsureDirTests(unittest.TestCase):
    def test_creates_nested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "a", "b", "c")
            ensure_dir(p)
            self.assertTrue(os.path.isdir(p))

    def test_existing_dir_is_no_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ensure_dir(tmp)  # should not raise
            self.assertTrue(os.path.isdir(tmp))


class RemovePathTests(unittest.TestCase):
    def test_remove_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "x.txt")
            with open(f, "w") as fh:
                fh.write("hi")
            remove_path(f)
            self.assertFalse(os.path.exists(f))

    def test_remove_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "sub")
            os.makedirs(d)
            with open(os.path.join(d, "a.txt"), "w") as fh:
                fh.write("a")
            remove_path(d)
            self.assertFalse(os.path.exists(d))

    def test_missing_is_no_error(self):
        remove_path("/nonexistent/whatever")


class SaveIVTextTests(unittest.TestCase):
    def test_writes_two_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "iv.txt")
            save_iv_text(p, [1.0, 0.5, 0.0], [1e-6, 2e-6, 3e-6])
            with open(p, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0], "1.0 0.5 0.0")
            self.assertEqual(lines[1], "1e-06 2e-06 3e-06")


class SaveSpectrumTextTests(unittest.TestCase):
    def test_writes_min_max_header_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "spec_")
            save_spectrum_text(p, "hist", [0.1, 0.5, -0.2, 0.3])
            full = p + "hist.txt"
            self.assertTrue(os.path.exists(full))
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            # first token-pairs are min and max
            tokens = content.split()
            self.assertEqual(float(tokens[0]), -0.2)
            self.assertEqual(float(tokens[1]), 0.5)
            # remaining are the values
            self.assertEqual([float(x) for x in tokens[2:]], [0.1, 0.5, -0.2, 0.3])


class WriteWaveformFileTests(unittest.TestCase):
    def test_writes_segment_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "run")
            os.makedirs(d)
            full = write_waveform_file(d, "1234.5", [0.1, 0.2, 0.3], 0)
            self.assertEqual(os.path.basename(full), "run_0.txt")
            with open(full, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0], "1234.5")
            self.assertEqual(lines[1], "wavedata")
            self.assertEqual(lines[2:], ["0.1", "0.2", "0.3"])


class WriteWaveformMetadataTests(unittest.TestCase):
    def test_writes_data_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "DATA.txt")
            write_waveform_metadata(p, 0.001, 1000, 1700000000.0, "1")
            with open(p, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0], "1700000000.0")
            self.assertIn("scope=1", lines[1])
            self.assertIn("time_base=0.001", lines[1])
            self.assertIn("num_points=1000", lines[1])


class CreateZipTests(unittest.TestCase):
    def test_zip_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "run")
            os.makedirs(d)
            with open(os.path.join(d, "a.txt"), "w") as f:
                f.write("hello")
            archive = create_zip(d, "run")
            self.assertTrue(os.path.isfile(archive))
            self.assertTrue(archive.endswith(".zip"))


if __name__ == "__main__":
    unittest.main()
