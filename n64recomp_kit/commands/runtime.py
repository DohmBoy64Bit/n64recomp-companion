from __future__ import annotations

import argparse

from ..runtime_template import generate_runtime_project
from ..util import print_json
from .common import add_json

COMMANDS = {"new-runtime-project"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("new-runtime-project", help="generate a Windows CMake starter with RT64, RmlUi, LunaSVG, and FreeType wiring")
    p.add_argument("--output", required=True, help="directory to create or update")
    p.add_argument("--name", required=True, help="project display name")
    p.add_argument("--window-title", help="window title shown by the SDL starter app")
    p.add_argument("--overwrite", action="store_true")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    report = generate_runtime_project(args.output, name=args.name, window_title=args.window_title, overwrite=args.overwrite)
    if args.json:
        print_json(report.to_dict())
    else:
        print(f"Wrote runtime starter: {report.root}")
        print(f"Files: {len(report.files)}")
    return 0
