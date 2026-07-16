import tempfile
import unittest
from pathlib import Path

from n64recomp_kit.matching import emit_matching_configure


class MatchingTests(unittest.TestCase):
    def test_emit_matching_configure(self):
        with tempfile.TemporaryDirectory() as td:
            report = emit_matching_configure(td, game="game_us")
            path = Path(report.path)
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertIn("game_us.z64", text)
            self.assertIn("mips-linux-gnu-as", text)

    def test_reject_bad_game_slug(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                emit_matching_configure(td, game="bad slug")


if __name__ == "__main__":
    unittest.main()
