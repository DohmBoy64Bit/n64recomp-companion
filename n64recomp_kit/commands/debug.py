from __future__ import annotations

import argparse

from ..cdb import discover_cdb, format_cdb_probe, write_cdb_evidence
from ..util import print_json
from .common import add_json

COMMANDS = {"cdb-info", "cdb-evidence"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("cdb-info", help="locate cdb.exe and project CDB PowerShell wrappers")
    p.add_argument("--root", default=".")
    add_json(p)

    p = sub.add_parser("cdb-evidence", help="write a CDB trace evidence note after a wrapper run")
    p.add_argument("--output", required=True)
    p.add_argument("--wrapper", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--result", required=True, choices=["HIT", "BYPASS", "ABORT", "INCONCLUSIVE"])
    p.add_argument("--breakpoint", action="append", default=[])
    p.add_argument("--summary", required=True)
    p.add_argument("--overwrite", action="store_true")


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "cdb-info":
        probe = discover_cdb(args.root)
        print_json(probe.to_dict()) if args.json else print(format_cdb_probe(probe))
        return 0 if probe.available else 2
    if args.command == "cdb-evidence":
        out = write_cdb_evidence(
            args.output,
            wrapper=args.wrapper,
            target=args.target,
            result=args.result,
            breakpoints=args.breakpoint,
            summary=args.summary,
            overwrite=args.overwrite,
        )
        print(f"Wrote {out}")
        return 0
    raise AssertionError(f"unhandled debug command: {args.command}")
