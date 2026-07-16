import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from n64recomp_kit.cli import main
from n64recomp_kit.runtime_template import generate_runtime_project


class RuntimeTemplateTests(unittest.TestCase):
    def test_generate_runtime_project_files(self):
        with tempfile.TemporaryDirectory() as td:
            report = generate_runtime_project(Path(td) / "starter", name="My Game", overwrite=False)
            root = Path(report.root)
            self.assertTrue((root / "CMakeLists.txt").exists())
            self.assertTrue((root / "Makefile").exists())
            self.assertTrue((root / "vcpkg.json").exists())
            self.assertTrue((root / "assets" / "ui" / "launcher.rml").exists())
            self.assertIn("rt64", (root / "cmake" / "Dependencies.cmake").read_text(encoding="utf-8"))
            self.assertIn("RmlUi::RmlUi", (root / "CMakeLists.txt").read_text(encoding="utf-8"))
            self.assertIn("lunasvg::lunasvg", (root / "CMakeLists.txt").read_text(encoding="utf-8"))
            self.assertIn("Freetype::Freetype", (root / "CMakeLists.txt").read_text(encoding="utf-8"))
            text_suffixes = {".txt", ".md", ".cpp", ".hpp", ".json", ".rml", ".rcss", ".svg", ".ps1", ".cmake"}
            combined = "\n".join(
                p.read_text(encoding="utf-8")
                for p in root.rglob("*")
                if p.is_file() and (p.suffix.lower() in text_suffixes or p.name == "Makefile")
            )
            self.assertNotIn("{{", combined)
            self.assertNotIn("}}", combined)

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as td:
            buf = StringIO()
            with redirect_stdout(buf):
                rc = main(["new-runtime-project", "--output", str(Path(td) / "starter"), "--name", "Runtime Test", "--json"])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["slug"], "runtime-test")
            self.assertGreater(data["file_count"], 10)


if __name__ == "__main__":
    unittest.main()
