import tempfile
import unittest
from pathlib import Path

from n64recomp_kit.toolchain import discover_mips_toolchains, format_toolchains, path_with_prefix
from n64recomp_kit.util import run_command


class ToolchainTests(unittest.TestCase):
    def test_fake_toolchain_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            bindir = Path(td)
            for name in ("as", "ld", "objdump", "readelf", "nm", "objcopy", "gcc"):
                tool = bindir / f"mips-test-{name}"
                tool.write_text("#!/usr/bin/env sh\necho 'fake tool 1.0'\n", encoding="utf-8")
                tool.chmod(0o755)
            env = path_with_prefix(bindir)
            result = run_command([
                env.get("PYTHON", "python3"),
                "-c",
                "from n64recomp_kit.toolchain import discover_mips_toolchains; "
                "print(discover_mips_toolchains(['mips-test-'])[0].complete_binutils)",
            ], env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("True", result.stdout)

    def test_format_empty(self):
        self.assertIn("No MIPS", format_toolchains([]))


if __name__ == "__main__":
    unittest.main()
