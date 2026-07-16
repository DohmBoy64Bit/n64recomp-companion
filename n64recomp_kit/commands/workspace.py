from __future__ import annotations

import argparse

from ..util import print_json
from ..workspace import format_workspace_scan, init_function_ledger, init_project_state, scan_workspace
from .common import add_json

COMMANDS = {"workspace-status", "init-state", "init-ledger"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("workspace-status", help="classify a project as matching-decomp or N64Recomp track and phase")
    p.add_argument("--root", default=".", help="project root to inspect")
    p.add_argument("--ignore-dir", action="append", default=[], help="directory name to skip; may be repeated")
    p.add_argument("--max-depth", type=int, default=6, help="maximum directory depth to inspect")
    add_json(p)

    p = sub.add_parser("init-state", help="write N64_PROJECT_STATE.md for repeatable long-running sessions")
    p.add_argument("--root", default=".")
    p.add_argument("--overwrite", action="store_true")

    p = sub.add_parser("init-ledger", help="write docs/function_ledger.md with evidence columns")
    p.add_argument("--root", default=".")
    p.add_argument("--overwrite", action="store_true")


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "workspace-status":
        scan = scan_workspace(args.root, ignore_dirs=args.ignore_dir, max_depth=args.max_depth)
        print_json(scan.to_dict()) if args.json else print(format_workspace_scan(scan))
        return 0
    if args.command == "init-state":
        out = init_project_state(args.root, overwrite=args.overwrite)
        print(f"Wrote {out}")
        return 0
    if args.command == "init-ledger":
        out = init_function_ledger(args.root, overwrite=args.overwrite)
        print(f"Wrote {out}")
        return 0
    raise AssertionError(f"unhandled workspace command: {args.command}")
