from __future__ import annotations

import argparse

from ..matching import emit_matching_configure, run_configure_min
from ..splat import create_splat_config, dump_symbols_csv, run_splat_config
from ..splat_repair import (
    apply_tail_split_hints,
    patch_data_asm,
    patch_tail_asm,
    recompiled_c_sanitize,
    suggest_tail_split_hints,
)
from ..util import parse_int, print_json, write_json
from .common import add_json

COMMANDS = {
    "emit-matching-configure",
    "matching-build",
    "splat-init",
    "splat-run",
    "patch-data-asm",
    "patch-tail-asm",
    "tail-split-hints",
    "apply-tail-split-hints",
    "recompiled-c-sanitize",
    "dump-symbols",
}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("emit-matching-configure", help="write an assembly-only configure.py for first ROM match attempts")
    p.add_argument("--root", default=".")
    p.add_argument("--game", required=True, help="game slug used for build output and linker script names")
    p.add_argument("--overwrite", action="store_true")
    add_json(p)

    p = sub.add_parser("matching-build", help="run a generated assembly-only configure.py")
    p.add_argument("--root", default=".")
    p.add_argument("--clean", action="store_true")
    p.add_argument("--build", action="store_true")
    p.add_argument("--diff", action="store_true")
    p.add_argument("--timeout", type=int)
    p.add_argument("--report", default="matching-build-report.json")
    add_json(p)

    p = sub.add_parser("splat-init", help="write a concrete Splat YAML config for a normalized .z64 ROM")
    p.add_argument("--config", required=True, help="output splat.yaml path")
    p.add_argument("--rom", required=True, help="normalized big-endian .z64 ROM path")
    p.add_argument("--basename", required=True, help="short project basename used by Splat outputs")
    p.add_argument("--compiler", default="IDO")
    p.add_argument("--code-start", default="0x1000")
    p.add_argument("--vram", default="0x80000400")
    p.add_argument("--end", help="exclusive ROM end offset, default is ROM size")
    p.add_argument("--overwrite", action="store_true")
    add_json(p)

    p = sub.add_parser("splat-run", help="run Splat on an existing YAML config and write a report")
    p.add_argument("config")
    p.add_argument("--splat", help="path to splat command")
    p.add_argument("--cwd", help="working directory for Splat")
    p.add_argument("--timeout", type=int)
    p.add_argument("--report", default="splat-report.json")
    add_json(p)

    p = sub.add_parser("patch-data-asm", help="annotate .word func_* data-pointer references in asm")
    p.add_argument("--asm-dir", required=True)
    p.add_argument("--symbol", action="append", default=[])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report")
    add_json(p)

    p = sub.add_parser("patch-tail-asm", help="rename duplicate non-function labels across tail asm files")
    p.add_argument("--asm-dir", required=True)
    p.add_argument("--prefix", default="tail_")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report")
    add_json(p)

    p = sub.add_parser("tail-split-hints", help="suggest Splat tail split hints from asm file names")
    p.add_argument("--asm-dir", required=True)
    p.add_argument("--min-gap", default="0x4000")
    p.add_argument("--output")
    add_json(p)

    p = sub.add_parser("apply-tail-split-hints", help="insert tail split hint subsegments into a Splat YAML")
    p.add_argument("--yaml", required=True)
    p.add_argument("--hints", required=True)
    p.add_argument("--segment", default="tail")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report")
    add_json(p)

    p = sub.add_parser("recompiled-c-sanitize", help="conservatively sanitize generated C/C++ files for host builds")
    p.add_argument("--path", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report")
    add_json(p)

    p = sub.add_parser("dump-symbols", help="run splat with dump_symbols and analyze the CSV cross-reference output")
    p.add_argument("--config", required=True)
    p.add_argument("--cwd", default=".")
    p.add_argument("--timeout", type=int)
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "emit-matching-configure":
        report = emit_matching_configure(args.root, game=args.game, overwrite=args.overwrite)
        print_json(report.to_dict()) if args.json else print(f"Wrote {report.path}")
        return 0
    if args.command == "matching-build":
        report = run_configure_min(args.root, clean=args.clean, build=args.build, diff=args.diff, timeout=args.timeout)
        write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print(f"Status: {'ok' if report['ok'] else 'failed'}")
            print(f"Report: {args.report}")
        return 0 if report["ok"] else 1
    if args.command == "splat-init":
        report = create_splat_config(
            args.config,
            rom_path=args.rom,
            basename=args.basename,
            compiler=args.compiler,
            code_start=parse_int(args.code_start),
            vram=parse_int(args.vram),
            end=parse_int(args.end) if args.end else None,
            overwrite=args.overwrite,
        )
        print_json(report.to_dict()) if args.json else print(f"Wrote {report.config}")
        return 0
    if args.command == "splat-run":
        report = run_splat_config(args.config, splat=args.splat, cwd=args.cwd, timeout=args.timeout)
        write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print(f"Status: {'ok' if report['ok'] else 'failed'}")
            print(f"Report: {args.report}")
            hints = report.get("hints", {})
            if hints.get("file_splits"):
                print(f"File split hints: {len(hints['file_splits'])} group(s)")
                for fs in hints["file_splits"]:
                    print(f"  {len(fs.get('splits', []))} suggested split(s) in segment {fs.get('segment', '?')}")
            if hints.get("rodata_pairings"):
                print(f"Rodata pairings: {len(hints['rodata_pairings'])}")
            if hints.get("rodata_starts"):
                print(f"Rodata start hints: {len(hints['rodata_starts'])}")
        return 0 if report["ok"] else 1
    if args.command == "patch-data-asm":
        data = patch_data_asm(asm_dir=args.asm_dir, symbols=args.symbol, dry_run=args.dry_run, report=args.report)
        print_json(data) if args.json else print(f"Annotated {data['replacement_count']} data references")
        return 0
    if args.command == "patch-tail-asm":
        data = patch_tail_asm(asm_dir=args.asm_dir, prefix=args.prefix, dry_run=args.dry_run, report=args.report)
        print_json(data) if args.json else print(f"Changed files: {data['changed_files']}")
        return 0
    if args.command == "tail-split-hints":
        data = suggest_tail_split_hints(asm_dir=args.asm_dir, min_gap=parse_int(args.min_gap), output=args.output)
        print_json(data) if args.json else print(f"Hints: {data['hint_count']}")
        return 0
    if args.command == "apply-tail-split-hints":
        data = apply_tail_split_hints(
            yaml_path=args.yaml,
            hints_file=args.hints,
            segment_name=args.segment,
            dry_run=args.dry_run,
            report=args.report,
        )
        print_json(data) if args.json else print(f"Added hints: {len(data['added'])}")
        return 0
    if args.command == "recompiled-c-sanitize":
        data = recompiled_c_sanitize(path=args.path, dry_run=args.dry_run, report=args.report)
        print_json(data) if args.json else print(f"Changed files: {len(data['changed_files'])}")
        return 0
    if args.command == "dump-symbols":
        data = dump_symbols_csv(args.config, cwd=args.cwd, timeout=args.timeout)
        if args.json:
            print_json(data)
        else:
            print(f"Total symbols: {data['total_symbols']}")
            print(f"Cross-references: {data['cross_references']}")
            if data.get("by_type"):
                print(f"By type: {data['by_type']}")
            if data.get("by_subsegment"):
                print(f"By subsegment ({len(data['by_subsegment'])}):")
                for name, count in sorted(data['by_subsegment'].items(), key=lambda x: -x[1])[:5]:
                    print(f"  {name}: {count}")
        return 0 if data["ok"] else 1
    raise AssertionError(f"unhandled matching command: {args.command}")
