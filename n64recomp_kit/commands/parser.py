from __future__ import annotations

import argparse

from . import debug, elf, environment, local_llm, matching, recomp, rom, runtime, suite, workspace

COMMAND_DOMAINS = (environment, workspace, rom, elf, matching, recomp, runtime, local_llm, debug, suite)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n64recomp-kit", description="Companion tools for N64Recomp workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    for domain in COMMAND_DOMAINS:
        domain.register(sub)
    return parser
