import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_support import ensure_minimal_fixtures

ensure_minimal_fixtures()

from n64recomp_kit.rom import convert_to_z64, detect_byte_order, inspect_rom


class RomTests(unittest.TestCase):
    def test_fixture_rom_info(self):
        info = inspect_rom(Path(__file__).parent / "fixtures" / "minimal.z64")
        self.assertEqual(info.byte_order, "z64-big-endian")
        self.assertEqual(info.title, "COMPANION TEST")
        self.assertEqual(info.entrypoint, "0x80000400")

    def test_v64_convert(self):
        src = Path(__file__).parent / "fixtures" / "minimal.v64"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.z64"
            report = convert_to_z64(src, out)
            self.assertEqual(report["source_byte_order"], "v64-byte-swapped-16")
            self.assertEqual(detect_byte_order(out.read_bytes()[:4]), "z64-big-endian")


if __name__ == "__main__":
    unittest.main()
