import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_support import ensure_minimal_fixtures

ensure_minimal_fixtures()

from n64recomp_kit.elf import inspect_elf


class ElfTests(unittest.TestCase):
    def test_minimal_mips_big_endian(self):
        info = inspect_elf(Path(__file__).parent / "fixtures" / "minimal_mips_be.elf")
        self.assertEqual(info.elf_class, "ELF32")
        self.assertEqual(info.endian, "big")
        self.assertEqual(info.machine, "MIPS")
        self.assertEqual(info.entrypoint, "0x80000400")
        self.assertEqual(len(info.executable_sections), 1)
        self.assertEqual(info.executable_sections[0].name, ".text")


if __name__ == "__main__":
    unittest.main()
