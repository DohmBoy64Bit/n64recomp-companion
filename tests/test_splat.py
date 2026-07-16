import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_support import ensure_minimal_fixtures

ensure_minimal_fixtures()

from n64recomp_kit.splat import create_splat_config, find_splat
from n64recomp_kit.cli import main


class SplatTests(unittest.TestCase):
    def test_create_splat_config(self):
        rom = Path(__file__).parent / "fixtures" / "minimal.z64"
        with tempfile.TemporaryDirectory() as td:
            padded = Path(td) / "game.z64"
            padded.write_bytes(rom.read_bytes() + b"\0" * 0x1000)
            cfg = Path(td) / "decomp" / "splat.yaml"
            report = create_splat_config(
                cfg,
                rom_path=padded,
                basename="fixture",
                code_start=0x1000,
                vram=0x80000400,
            )
            text = cfg.read_text()
            self.assertEqual(report.basename, "fixture")
            self.assertIn("platform: n64", text)
            self.assertIn("splat.yaml", report.config)
            self.assertIn("find_file_boundaries: True", text)
            self.assertTrue((Path(td) / "decomp" / "asm").is_dir())

    def test_find_splat_next_to_current_python(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sibling = root / ("splat.exe" if sys.platform == "win32" else "splat")
            sibling.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            sibling.chmod(0o755)
            python_link = root / "python"
            try:
                python_link.symlink_to(Path(sys.executable))
            except OSError:
                python_link.write_text("", encoding="utf-8")
            with patch("n64recomp_kit.splat.which", return_value=None), patch(
                "n64recomp_kit.splat.sys.executable", str(python_link)
            ):
                self.assertEqual(find_splat(), str(sibling))

    def test_splat_init_cli(self):
        rom = Path(__file__).parent / "fixtures" / "minimal.z64"
        with tempfile.TemporaryDirectory() as td:
            padded = Path(td) / "game.z64"
            padded.write_bytes(rom.read_bytes() + b"\0" * 0x1000)
            cfg = Path(td) / "splat.yaml"
            rc = main([
                "splat-init",
                "--config", str(cfg),
                "--rom", str(padded),
                "--basename", "fixture",
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(cfg.is_file())


if __name__ == "__main__":
    unittest.main()
