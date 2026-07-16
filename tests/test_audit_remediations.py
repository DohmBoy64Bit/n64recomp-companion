import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from n64recomp_kit.config import validate_config
from n64recomp_kit.elf_build import build_elf_from_splat, load_elf_build_paths
from n64recomp_kit.ignore_workflow import recomp_smoke
from n64recomp_kit.matching import emit_matching_configure
from n64recomp_kit.recomp import run_recomp
from n64recomp_kit.rom_match import rom_build_from_map, rom_match_sections
from n64recomp_kit.runtime_template import generate_runtime_project
from n64recomp_kit.splat import run_splat_config
from n64recomp_kit.toolchain import ToolProbe, ToolchainProbe
from n64recomp_kit.util import CommandResult, validate_safe_delete_target

FIXTURES = Path(__file__).parent / "fixtures"


def ok_result(command):
    return CommandResult(list(command), 0, "", "", 0.01)


class AuditRemediationTests(unittest.TestCase):
    def test_splat_uses_split_subcommand(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "splat.yaml"
            cfg.write_text("options:\n  basename: x\nsegments: []\n", encoding="utf-8")
            with patch("n64recomp_kit.splat.find_splat", return_value="splat"), patch(
                "n64recomp_kit.splat.run_command", side_effect=lambda command, **_: ok_result(command)
            ) as run:
                report = run_splat_config(cfg)
            self.assertTrue(report["ok"])
            self.assertEqual(run.call_args.args[0][0:2], ["splat", "split"])
            self.assertEqual(Path(run.call_args.args[0][2]), cfg.resolve())

    def test_splat_base_path_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "decomp" / "splat.yaml"
            cfg.parent.mkdir()
            cfg.write_text(
                "options:\n  base_path: split\n  basename: starfall\n  asm_path: asm\n  src_path: src\n  build_path: build\n  ld_script_path: starfall.ld\n  elf_path: build/starfall.elf\nsegments: []\n",
                encoding="utf-8",
            )
            paths = load_elf_build_paths(cfg, root_path=root)
            base = (cfg.parent / "split").resolve()
            self.assertEqual(Path(paths.base_path), base)
            self.assertEqual(Path(paths.asm_path), base / "asm")
            self.assertEqual(Path(paths.elf_path), base / "build" / "starfall.elf")

    def test_real_elf_build_accepts_valid_mips_elf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "split" / "asm").mkdir(parents=True)
            (root / "split" / "asm" / "boot.s").write_text("nop\n", encoding="utf-8")
            (root / "split" / "starfall.ld").write_text("SECTIONS {}\n", encoding="utf-8")
            cfg = root / "splat.yaml"
            cfg.write_text(
                "options:\n  base_path: split\n  basename: starfall\n  asm_path: asm\n  build_path: build\n  ld_script_path: starfall.ld\n  elf_path: build/starfall.elf\nsegments: []\n",
                encoding="utf-8",
            )
            tools = [ToolProbe(name, f"mips-{name}", f"/fake/mips-{name}", True) for name in ["as", "ld", "readelf", "objdump", "nm", "objcopy"]]
            probe = ToolchainProbe("mips-", tools, True, False)

            def run(command, **_):
                if command[0].endswith("ld"):
                    output = Path(command[command.index("-o") + 1])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes((FIXTURES / "minimal_mips_be.elf").read_bytes())
                return ok_result(command)

            with patch("n64recomp_kit.elf_build.choose_toolchain", return_value=probe), patch(
                "n64recomp_kit.elf_build.run_command", side_effect=run
            ):
                report = build_elf_from_splat(cfg, root_path=root)
            self.assertTrue(report.ok)
            self.assertEqual(report.elf_info["machine"], "MIPS")
            self.assertEqual(report.elf_info["endian"], "big")

    def test_nested_recomp_config_passes_basename_in_config_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_dir = root / "decomp"
            cfg_dir.mkdir()
            elf = cfg_dir / "game.elf"
            elf.write_bytes((FIXTURES / "minimal_mips_be.elf").read_bytes())
            cfg = cfg_dir / "game.recomp.toml"
            cfg.write_text('[input]\nentrypoint = 0x80000400\nelf_path = "game.elf"\noutput_func_path = "RecompiledFuncs"\n', encoding="utf-8")
            calls = []
            with patch("n64recomp_kit.recomp.find_n64recomp", return_value=str(root / "N64Recomp.exe")), patch(
                "n64recomp_kit.recomp.run_command", side_effect=lambda command, **kw: calls.append((command, kw)) or ok_result(command)
            ):
                report = run_recomp(cfg)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(calls[0][0][1], cfg.name)
            self.assertEqual(Path(calls[0][1]["cwd"]), cfg_dir.resolve())

    def test_matching_generator_has_distinct_elf_and_raw_binary_steps(self):
        with tempfile.TemporaryDirectory() as td:
            report = emit_matching_configure(td, game="starfall", overwrite=True)
            text = Path(report.path).read_text(encoding="utf-8")
            self.assertIn('TARGET_ELF = BUILD_DIR / "starfall.elf"', text)
            self.assertIn('TARGET_ROM = BUILD_DIR / "starfall.z64"', text)
            self.assertIn('rule binary', text)
            self.assertIn('objcopy', text.lower())
            self.assertNotIn('cmp -', text)

    def test_recomp_smoke_uses_updated_iteration_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            elf = root / "game.elf"
            elf.write_bytes((FIXTURES / "minimal_mips_be.elf").read_bytes())
            cfg = root / "game.toml"
            cfg.write_text('[input]\nentrypoint=0x80000400\nelf_path="game.elf"\noutput_func_path="out"\n[patches]\nignored=[]\n', encoding="utf-8")
            seen = []

            def fake_run(config, **_):
                text = Path(config).read_text(encoding="utf-8")
                seen.append(text)
                if len(seen) == 1:
                    return {"status": "failed", "n64recomp": "fake", "command": {"stdout": "failed function func_80001000", "stderr": ""}}
                return {"status": "ok", "n64recomp": "fake", "command": {"stdout": "", "stderr": ""}}

            with patch("n64recomp_kit.ignore_workflow.run_recomp", side_effect=fake_run):
                report = recomp_smoke(config=cfg, max_iterations=3)
            self.assertTrue(report["ok"])
            self.assertEqual(len(seen), 2)
            self.assertNotIn("func_80001000", seen[0])
            self.assertIn("func_80001000", seen[1])

    def test_runtime_manifest_enables_rmlui_svg_and_pins_rt64(self):
        with tempfile.TemporaryDirectory() as td:
            generate_runtime_project(td, name="Starfall64", overwrite=True)
            manifest = json.loads((Path(td) / "vcpkg.json").read_text(encoding="utf-8"))
            rml = next(item for item in manifest["dependencies"] if isinstance(item, dict) and item.get("name") == "rmlui")
            self.assertIn("svg", rml["features"])
            self.assertEqual(manifest["builtin-baseline"], "cd61e1e26a038e82d6550a3ebbe0fbbfe7da78e3")
            cmake = (Path(td) / "cmake" / "Dependencies.cmake").read_text(encoding="utf-8")
            self.assertIn("f0728a2520d5aa735886240de3fee75cc805f6d6", cmake)

    def test_unknown_config_key_warns_and_mdebug_is_validated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            elf = root / "x.elf"
            elf.write_bytes((FIXTURES / "minimal_mips_be.elf").read_bytes())
            cfg = root / "x.toml"
            cfg.write_text(
                '[input]\nelf_path="x.elf"\noutput_func_path="out"\nmisspelled=true\nmdebug_file_mappings=[{filename="x.c", input_section=".text", output_section=".text"}]\n',
                encoding="utf-8",
            )
            result = validate_config(cfg)
            self.assertTrue(result.ok)
            self.assertTrue(any(d.severity == "warning" and d.key == "input.misspelled" for d in result.diagnostics))

    def test_delete_guard_and_map_validation(self):
        with self.assertRaises(ValueError):
            validate_safe_delete_target(Path.cwd())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            protected = root / "project" / "decomp"
            protected.mkdir(parents=True)
            with self.assertRaises(ValueError):
                validate_safe_delete_target(root / "project", protected=[protected])
            empty = root / "empty.map"
            empty.write_text("# no entries\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rom_build_from_map(map_file=empty, output=root / "out.bin")
            malformed = root / "bad.map"
            malformed.write_text("not a valid line\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rom_build_from_map(map_file=malformed, output=root / "out.bin")

    def test_section_manifest_paths_are_relative_to_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "expected.bin").write_bytes(b"abcd")
            (root / "actual.bin").write_bytes(b"abcd")
            manifest = root / "sections.json"
            manifest.write_text(json.dumps({"sections": [{"name": "x", "expected": "expected.bin", "actual": "actual.bin", "expected_offset": 0, "actual_offset": 0, "size": 4}]}), encoding="utf-8")
            old = Path.cwd()
            try:
                import os
                os.chdir(old.parent)
                report = rom_match_sections(manifest=manifest)
            finally:
                os.chdir(old)
            self.assertTrue(report["ok"])


if __name__ == "__main__":
    unittest.main()

class AdditionalAuditRemediationTests(unittest.TestCase):
    def test_unknown_top_level_config_key_warns(self):
        from n64recomp_kit.config import validate_config
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            elf = root / "input.elf"
            elf.write_bytes((Path(__file__).parent / "fixtures" / "minimal_mips_be.elf").read_bytes())
            config = root / "game.toml"
            config.write_text(
                '[input]\nelf_path = "input.elf"\noutput_func_path = "RecompiledFuncs"\n\n[extra]\nvalue = 1\n',
                encoding="utf-8",
            )
            result = validate_config(config)
            self.assertTrue(result.ok)
            self.assertTrue(any(d.key == "extra" and d.severity == "warning" for d in result.diagnostics))

    def test_allowed_alias_is_not_reported_as_overlap(self):
        from n64recomp_kit.audit import elf_symbol_audit
        with tempfile.TemporaryDirectory() as td:
            symbols = Path(td) / "symbols.txt"
            symbols.write_text(
                "   1: 80100000    16 FUNC    GLOBAL DEFAULT    1 func_80100000\n"
                "   2: 80100000    16 FUNC    GLOBAL DEFAULT    1 alias_80100000\n",
                encoding="utf-8",
            )
            report = elf_symbol_audit(symbols_file=symbols, alias_policy="allow")
            self.assertTrue(report["ok"])
            self.assertEqual(report["alias_count"], 1)
            self.assertEqual(report["issues"]["overlaps"], [])
