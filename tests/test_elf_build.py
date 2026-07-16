import json
import tempfile
import unittest
from pathlib import Path

from n64recomp_kit.cli import main
from n64recomp_kit.elf_build import build_elf_from_splat, emit_elf_build_helpers, load_elf_build_paths, read_splat_options


class ElfBuildTests(unittest.TestCase):
    def make_workspace(self, td: str) -> Path:
        root = Path(td)
        (root / "decomp" / "asm").mkdir(parents=True)
        (root / "decomp" / "src").mkdir(parents=True)
        (root / "decomp" / "build").mkdir(parents=True)
        (root / "decomp" / "asm" / "boot.s").write_text(".section .text\n.globl entry\nentry:\n  nop\n", encoding="utf-8")
        (root / "decomp" / "game_us.ld").write_text("ENTRY(entry)\nSECTIONS { . = 0x80000400; .text : { *(.text*) } }\n", encoding="utf-8")
        (root / "decomp" / "splat.yaml").write_text(
            "options:\n"
            "  basename: \"game_us\"\n"
            "  base_path: \"decomp\"\n"
            "  asm_path: \"decomp/asm\"\n"
            "  src_path: \"decomp/src\"\n"
            "  build_path: \"decomp/build\"\n"
            "  ld_script_path: \"decomp/game_us.ld\"\n"
            "  elf_path: \"decomp/build/game_us.elf\"\n"
            "segments:\n"
            "  - name: header\n"
            "    type: header\n",
            encoding="utf-8",
        )
        return root

    def test_read_splat_options(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_workspace(td)
            options = read_splat_options(root / "decomp" / "splat.yaml")
            self.assertEqual(options["basename"], "game_us")
            self.assertEqual(options["elf_path"], "decomp/build/game_us.elf")

    def test_load_paths_from_splat(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_workspace(td)
            paths = load_elf_build_paths("decomp/splat.yaml", root_path=root)
            self.assertTrue(paths.elf_path.endswith("decomp/build/game_us.elf"))
            self.assertEqual(paths.basename, "game_us")

    def test_build_elf_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_workspace(td)
            report = build_elf_from_splat("decomp/splat.yaml", root_path=root, dry_run=True)
            self.assertTrue(report.ok)
            self.assertTrue(report.dry_run)
            self.assertEqual(report.object_count, 1)
            flat = " ".join(" ".join(command) for command in report.commands)
            self.assertIn("mips-linux-gnu-as", flat)
            self.assertIn("mips-linux-gnu-ld", flat)

    def test_emit_helpers(self):
        with tempfile.TemporaryDirectory() as td:
            report = emit_elf_build_helpers(td)
            self.assertEqual(len(report["files"]), 2)
            for path in report["files"]:
                self.assertTrue(Path(path).is_file())

    def test_cli_build_elf_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_workspace(td)
            report_path = root / "build" / "elf.json"
            rc = main([
                "build-elf",
                "--config", "decomp/splat.yaml",
                "--root", str(root),
                "--dry-run",
                "--report", str(report_path),
            ])
            self.assertEqual(rc, 0)
            data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertEqual(data["object_count"], 1)


if __name__ == "__main__":
    unittest.main()
