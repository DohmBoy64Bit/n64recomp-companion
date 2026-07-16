import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_support import ensure_minimal_fixtures

ensure_minimal_fixtures()

from n64recomp_kit.cli import main


class CliTests(unittest.TestCase):
    def test_check_config_cli(self):
        rc = main(["check-config", "tests/fixtures/valid_elf_config.toml"])
        self.assertEqual(rc, 0)

    def test_elf_info_cli(self):
        rc = main(["elf-info", "tests/fixtures/minimal_mips_be.elf"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

class CliArchitectureTests(unittest.TestCase):
    def test_domain_command_sets_are_disjoint_and_complete(self):
        import argparse
        from n64recomp_kit.commands import debug, elf, environment, local_llm, matching, recomp, rom, runtime, suite, workspace
        from n64recomp_kit.commands.parser import build_parser

        domains = [
            environment.COMMANDS,
            workspace.COMMANDS,
            rom.COMMANDS,
            elf.COMMANDS,
            matching.COMMANDS,
            recomp.COMMANDS,
            runtime.COMMANDS,
            local_llm.COMMANDS,
            debug.COMMANDS,
            suite.COMMANDS,
        ]
        for index, current in enumerate(domains):
            for other in domains[index + 1 :]:
                self.assertFalse(current & other)
        expected = set().union(*domains)
        self.assertEqual(len(expected), 43)

        parser = build_parser()
        action = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        self.assertEqual(set(action.choices), expected)
