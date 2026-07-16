import tempfile
import unittest
from pathlib import Path

from n64recomp_kit.workspace import init_function_ledger, init_project_state, scan_workspace


class WorkspaceTests(unittest.TestCase):
    def test_phase_zero_rom(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "baserom.z64").write_bytes(b"dummy")
            scan = scan_workspace(root)
            self.assertIn("Track A", scan.track)
            self.assertIn("0", scan.phase)

    def test_recomp_runtime_gap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "game.recomp.toml").write_text("[input]\noutput_func_path = 'RecompiledFuncs'\nelf_path = 'game.elf'\n", encoding="utf-8")
            (root / "RecompiledFuncs").mkdir()
            scan = scan_workspace(root)
            self.assertIn("Track B", scan.track)
            self.assertTrue(any("RecompiledFuncs" in gap for gap in scan.gaps))

    def test_state_and_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = init_project_state(root)
            ledger = init_function_ledger(root)
            self.assertTrue(state.is_file())
            self.assertTrue(ledger.is_file())


if __name__ == "__main__":
    unittest.main()
