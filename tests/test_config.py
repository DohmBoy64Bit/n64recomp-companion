import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_support import ensure_minimal_fixtures

ensure_minimal_fixtures()

from n64recomp_kit.config import create_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_valid_fixture_config(self):
        cfg = Path(__file__).parent / "fixtures" / "valid_elf_config.toml"
        result = validate_config(cfg)
        self.assertTrue(result.ok, [d.to_dict() for d in result.diagnostics])

    def test_generated_config_validates(self):
        fixtures = Path(__file__).parent / "fixtures"
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "project.toml"
            create_config(
                cfg,
                entrypoint=0x80000400,
                elf_path=str(fixtures / "minimal_mips_be.elf"),
                rom_path=None,
                symbols_file_path=None,
                output_func_path="RecompiledFuncs",
                overwrite=True,
            )
            result = validate_config(cfg)
            self.assertTrue(result.ok, [d.to_dict() for d in result.diagnostics])

    def test_bad_alignment_fails(self):
        fixtures = Path(__file__).parent / "fixtures"
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "bad.toml"
            cfg.write_text(f"""[input]\nentrypoint = 0x80000402\nelf_path = \"{fixtures / 'minimal_mips_be.elf'}\"\noutput_func_path = \"RecompiledFuncs\"\n""")
            result = validate_config(cfg)
            self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
