import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from n64recomp_kit.cli import main
from n64recomp_kit.real_rom_suite import run_real_rom_suite

FIXTURES = Path(__file__).parent / "fixtures"


class RealRomSuiteTests(unittest.TestCase):
    @staticmethod
    def _real_sized_rom(root: Path) -> Path:
        rom = root / "sample.z64"
        rom.write_bytes((FIXTURES / "minimal.z64").read_bytes() + b"\0" * 0x2000)
        return rom

    def test_safe_suite_uses_real_rom_and_writes_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rom = self._real_sized_rom(root)
            report = run_real_rom_suite(
                rom=rom,
                project_root=root,
                output_dir="build/real-rom-test",
                source_root=Path(__file__).resolve().parents[1],
            )
            self.assertTrue(report.ok)
            self.assertFalse(report.complete)
            self.assertEqual(report.counts["fail"], 0)
            out = root / "build" / "real-rom-test"
            self.assertTrue((out / "real-rom-test-report.json").is_file())
            self.assertTrue((out / "real-rom-test-report.md").is_file())
            self.assertEqual(report.rom["normalized_sha256"], report.rom["sha256"])
            checks = {check.check_id: check for check in report.checks}
            self.assertEqual(checks["rom.inspect"].status, "pass")
            self.assertEqual(checks["generated.runtime-project"].status, "pass")
            self.assertEqual(checks["synthetic.asm-repair"].status, "pass")
            self.assertEqual(checks["external.splat-split"].status, "skip")

    def test_supplied_splat_config_executes_when_splat_is_available(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "splat.yaml"
            config.write_text("segments: []\n", encoding="utf-8")
            with patch("n64recomp_kit.real_rom_suite.find_splat", return_value="splat"), patch(
                "n64recomp_kit.real_rom_suite.run_splat_config",
                return_value={"ok": True, "returncode": 0},
            ):
                report = run_real_rom_suite(
                    rom=self._real_sized_rom(root),
                    project_root=root,
                    output_dir="suite",
                    splat_config=config,
                    execute=["splat"],
                    strict=True,
                )
            self.assertTrue(report.ok)
            check = next(item for item in report.checks if item.check_id == "external.splat-split")
            self.assertEqual(check.status, "pass")

    def test_requested_splat_is_blocked_without_review_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_real_rom_suite(
                rom=self._real_sized_rom(root),
                project_root=root,
                output_dir="suite",
                execute=["splat"],
                strict=True,
            )
            self.assertFalse(report.ok)
            check = next(item for item in report.checks if item.check_id == "external.splat-split")
            self.assertEqual(check.status, "blocked")

    def test_cli_safe_suite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rc = main(
                [
                    "real-rom-test",
                    "--rom",
                    str(self._real_sized_rom(root)),
                    "--project-root",
                    td,
                    "--output",
                    "suite",
                ]
            )
            self.assertEqual(rc, 0)

    def test_requested_mips_without_toolchain_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch("n64recomp_kit.real_rom_suite.discover_mips_toolchains", return_value=[]):
                report = run_real_rom_suite(
                    rom=self._real_sized_rom(root),
                    project_root=root,
                    output_dir="suite",
                    execute=["mips"],
                    strict=True,
                )
            self.assertFalse(report.ok)
            check = next(item for item in report.checks if item.check_id == "external.mips-smoke")
            self.assertEqual(check.status, "blocked")
            self.assertEqual(report.counts["fail"], 0)

    def test_suite_module_imports_without_cli_preload(self):
        result = subprocess.run(
            [sys.executable, "-c", "import n64recomp_kit.real_rom_suite"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_llm_stage_runs_capability_probe_and_completion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doctor_result = {"tool_call_probe": {"supported": True}}
            completion_result = {"ok": True, "tool_rounds": 0, "answer": "received"}
            with patch("n64recomp_kit.real_rom_suite.local_llm_doctor", return_value=doctor_result), patch(
                "n64recomp_kit.real_rom_suite.local_llm_ask", return_value=completion_result
            ):
                report = run_real_rom_suite(
                    rom=self._real_sized_rom(root),
                    project_root=root,
                    output_dir="suite",
                    execute=["llm"],
                    model="local-test-model",
                    strict=True,
                )
            self.assertTrue(report.ok)
            checks = {item.check_id: item for item in report.checks}
            self.assertEqual(checks["external.llm-probe"].status, "pass")
            self.assertEqual(checks["external.llm-completion"].status, "pass")
            self.assertEqual(checks["external.llm-completion"].evidence["answer_length"], 8)


if __name__ == "__main__":
    unittest.main()
