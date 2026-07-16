import tempfile
import unittest
from pathlib import Path

from n64recomp_kit.cdb import discover_cdb, write_cdb_evidence


class CdbTests(unittest.TestCase):
    def test_discover_wrappers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "tools" / "run_game_cdb.ps1").write_text("Write-Host test", encoding="utf-8")
            probe = discover_cdb(root)
            self.assertIn("tools/run_game_cdb.ps1", probe.wrappers)

    def test_write_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "trace.md"
            write_cdb_evidence(out, wrapper="tools/run.ps1", target="build/game.exe", result="HIT", breakpoints=["game!main"], summary="Hit once.")
            text = out.read_text(encoding="utf-8")
            self.assertIn("Result: HIT", text)
            self.assertIn("game!main", text)


if __name__ == "__main__":
    unittest.main()
