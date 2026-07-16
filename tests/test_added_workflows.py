import json
import tempfile
import unittest
from pathlib import Path

from n64recomp_kit.audit import elf_symbol_audit, export_functions, filter_ignored_by_export
from n64recomp_kit.cli import main
from n64recomp_kit.ignore_workflow import scan_unsupported, sync_ignored_toml
from n64recomp_kit.rom_match import rom_build_from_map, rom_match_check, rom_match_sections
from n64recomp_kit.splat_repair import apply_tail_split_hints, mips_link_preflight, patch_data_asm, patch_tail_asm, suggest_tail_split_hints

READELF = """
Symbol table '.symtab' contains 5 entries:
   Num:    Value  Size Type    Bind   Vis      Ndx Name
     1: 80100000    16 FUNC    GLOBAL DEFAULT    1 func_80100000
     2: 80100010     0 FUNC    GLOBAL DEFAULT    1 func_80100010
     3: 80100020     8 FUNC    GLOBAL DEFAULT  UND func_80100020
     4: 80100030     4 OBJECT  GLOBAL DEFAULT    2 D_80100030
     5: 80100040    12 FUNC    GLOBAL DEFAULT    1 jtbl_80100040
     6: 80100050    20 FUNC    GLOBAL DEFAULT    1 func_80100050
"""

class AddedWorkflowTests(unittest.TestCase):
    def test_export_and_audit_symbols(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sym = root / "readelf.txt"
            sym.write_text(READELF, encoding="utf-8")
            report = export_functions(symbols_file=sym, out_dir=root / "symbols", ranges=["main:0x80100000:0x80100100"])
            self.assertEqual(report["exported_functions"], 2)
            tsv = (root / "symbols" / "sized-funcs.tsv").read_text(encoding="utf-8")
            self.assertIn("func_80100000", tsv)
            self.assertNotIn("jtbl_80100040", tsv)
            audit = elf_symbol_audit(symbols_file=sym)
            self.assertFalse(audit["ok"])
            self.assertEqual(audit["issue_count"], 2)

    def test_filter_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sized = root / "sized.tsv"
            sized.write_text("# h\n0x80100000\t16\tfunc_80100000\t1\tmain\n", encoding="utf-8")
            ignored = root / "ignored.txt"
            ignored.write_text("func_80100000\nfunc_80100010\n", encoding="utf-8")
            report = filter_ignored_by_export(sized_tsv=sized, ignored_files=[ignored])
            self.assertEqual(report["total_dropped"], 1)
            self.assertNotIn("func_80100010", ignored.read_text(encoding="utf-8"))

    def test_scan_and_sync_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            asm = root / "asm"
            asm.mkdir()
            (asm / "a.s").write_text("glabel func_80100000\n  trunc.l.d $f0, $f2\nendlabel\nglabel func_80100010\n  jal func_80001000\nendlabel\n", encoding="utf-8")
            scan = scan_unsupported(asm_dir=asm, out_dir=root / "symbols")
            self.assertIn("func_80100000", scan.genuine_ignored)
            self.assertIn("func_80100010", scan.low_func_callers)
            toml = root / "game.toml"
            toml.write_text('[input]\noutput_func_path="out"\nelf_path="game.elf"\n\n[patches]\nignored = ["func_80000000"]\n', encoding="utf-8")
            report = sync_ignored_toml(config=toml, ignored_files=[root / "symbols" / "ignored-genuine.txt"])
            self.assertEqual(report["ignored_count"], 2)
            updated = toml.read_text(encoding="utf-8")
            self.assertIn('"func_80000000"', updated)
            self.assertIn('"func_80100000"', updated)

    def test_rom_match_and_build_from_map(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.bin"
            actual = root / "actual.bin"
            expected.write_bytes(b"AAAABBBB")
            actual.write_bytes(b"AAAABBBX")
            self.assertFalse(rom_match_check(expected=expected, actual=actual)["ok"])
            manifest = root / "sections.json"
            manifest.write_text(json.dumps({"sections": [{"name": "head", "expected": str(expected), "actual": str(actual), "offset": 0, "size": 4}]}), encoding="utf-8")
            self.assertTrue(rom_match_sections(manifest=manifest)["ok"])
            part = root / "part.bin"
            part.write_bytes(b"HI")
            map_file = root / "map.txt"
            map_file.write_text("0x0 0x2 part.bin\n", encoding="utf-8")
            out = root / "out.bin"
            built = rom_build_from_map(map_file=map_file, output=out, root=root)
            self.assertTrue(built["ok"])
            self.assertEqual(out.read_bytes(), b"HI")

    def test_splat_repair_and_preflight(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            asm = root / "asm"
            asm.mkdir()
            (asm / "tail_10000.s").write_text("lbl:\n  b lbl\n  .word func_80100000\n", encoding="utf-8")
            (asm / "tail_20000.s").write_text("lbl:\n  b lbl\n", encoding="utf-8")
            data = patch_data_asm(asm_dir=asm)
            self.assertEqual(data["replacement_count"], 1)
            tail = patch_tail_asm(asm_dir=asm)
            self.assertEqual(tail["changed_files"], 2)
            hints = suggest_tail_split_hints(asm_dir=asm, output=root / "hints.txt")
            self.assertGreaterEqual(hints["hint_count"], 1)
            yaml = root / "splat.yaml"
            yaml.write_text("segments:\n  - name: tail\n    type: code\n    subsegments:\n      - [0x10000, asm, tail]\n", encoding="utf-8")
            applied = apply_tail_split_hints(yaml_path=yaml, hints_file=root / "hints.txt")
            self.assertTrue(applied["ok"])
            (root / "decomp" / "asm").mkdir(parents=True)
            (root / "decomp" / "asm" / "boot.s").write_text(".section .text\n", encoding="utf-8")
            (root / "decomp" / "game.ld").write_text("SECTIONS{}\n", encoding="utf-8")
            (root / "decomp" / "splat2.yaml").write_text("options:\n  basename: game\n  asm_path: decomp/asm\n  build_path: decomp/build\n  ld_script_path: decomp/game.ld\n  elf_path: decomp/build/game.elf\n", encoding="utf-8")
            pre = mips_link_preflight(config="decomp/splat2.yaml", root=root, dry_run=True)
            self.assertTrue(pre["ok"])

    def test_cli_new_commands(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sym = root / "readelf.txt"
            sym.write_text(READELF, encoding="utf-8")
            self.assertEqual(main(["export-functions", "--symbols-file", str(sym), "--out-dir", str(root / "sym")]), 0)
            self.assertNotEqual(main(["elf-symbol-audit", "--symbols-file", str(sym)]), 0)
            asm = root / "asm"; asm.mkdir()
            (asm / "a.s").write_text("glabel func_80100000\ntrunc.l.s $f0,$f2\n", encoding="utf-8")
            self.assertEqual(main(["scan-unsupported", "--asm-dir", str(asm), "--out-dir", str(root / "out")]), 0)

if __name__ == "__main__":
    unittest.main()
