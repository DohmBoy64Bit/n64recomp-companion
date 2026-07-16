from __future__ import annotations

import argparse
import sys

from . import debug, elf, environment, local_llm, matching, recomp, rom, runtime, suite, workspace
from .common import CommandHandler

HANDLERS: tuple[CommandHandler, ...] = (
    environment.handle,
    workspace.handle,
    rom.handle,
    elf.handle,
    matching.handle,
    recomp.handle,
    runtime.handle,
    local_llm.handle,
    debug.handle,
    suite.handle,
)


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        for handler in HANDLERS:
            result = handler(args)
            if result is not None:
                return result
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2
