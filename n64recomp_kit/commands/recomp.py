from __future__ import annotations

import argparse

from ..batch import run_batch
from ..config import create_config, format_validation, validate_config
from ..ignore_workflow import recomp_smoke, scan_unsupported, sync_ignored_toml
from ..recomp import format_summary, run_recomp, summarize_output
from ..util import parse_int, print_json, write_json
from .common import add_json

COMMANDS = {
    "scan-unsupported",
    "sync-ignored",
    "recomp-smoke",
    "init",
    "check-config",
    "run",
    "summarize-output",
    "batch",
}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("scan-unsupported", help="scan Splat asm for known unsupported N64Recomp instructions")
    p.add_argument("--asm-dir", required=True)
    p.add_argument("--out-dir", default="symbols/recomp")
    add_json(p)

    p = sub.add_parser("sync-ignored", help="sync [patches].ignored in an N64Recomp TOML from ignored list files")
    p.add_argument("--config", required=True)
    p.add_argument("--ignored", action="append", required=True, help="ignored list file; may be repeated")
    p.add_argument("--output", help="write to another TOML instead of modifying --config")
    p.add_argument("--dry-run", action="store_true")
    add_json(p)

    p = sub.add_parser("recomp-smoke", help="iterate N64Recomp runs and collect failing functions into an ignore list")
    p.add_argument("--config", required=True)
    p.add_argument("--n64recomp", help="path to N64Recomp binary")
    p.add_argument("--max-iterations", type=int, default=5)
    p.add_argument("--ignored-file")
    p.add_argument("--clean-output", action="store_true")
    p.add_argument("--timeout", type=int)
    p.add_argument("--allow-missing-paths", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report", default="recomp-smoke-report.json")
    add_json(p)

    p = sub.add_parser("init", help="write a concrete N64Recomp TOML config")
    p.add_argument("--config", required=True, help="output TOML path")
    p.add_argument("--entrypoint", help="entrypoint integer, decimal or 0x hex")
    p.add_argument("--elf", help="ELF input path")
    p.add_argument("--rom", help="ROM input path for symbol-file mode")
    p.add_argument("--symbols", help="N64Recomp symbols TOML path for symbol-file mode")
    p.add_argument("--output-func-path", default="RecompiledFuncs")
    p.add_argument("--relocatable-sections-path")
    p.add_argument("--single-file-output", action="store_true")
    p.add_argument("--functions-per-output-file", type=int, default=50)
    p.add_argument("--recomp-include", default='#include "recomp.h"')
    p.add_argument("--overwrite", action="store_true")

    p = sub.add_parser("check-config", help="validate an N64Recomp TOML config")
    p.add_argument("config")
    p.add_argument("--allow-missing-paths", action="store_true")
    add_json(p)

    p = sub.add_parser("run", help="validate and run N64Recomp")
    p.add_argument("config")
    p.add_argument("--n64recomp", help="path to N64Recomp binary")
    p.add_argument("--clean-output", action="store_true")
    p.add_argument("--timeout", type=int)
    p.add_argument("--allow-missing-paths", action="store_true")
    p.add_argument("--report", default="recomp-report.json")
    add_json(p)

    p = sub.add_parser("summarize-output", help="summarize generated recompilation output")
    p.add_argument("path")
    p.add_argument("--largest", type=int, default=10)
    add_json(p)

    p = sub.add_parser("batch", help="batch-check or batch-run several configs")
    p.add_argument("manifest")
    p.add_argument("--mode", choices=["check", "run"], default="check")
    p.add_argument("--n64recomp", help="path to N64Recomp binary")
    p.add_argument("--clean-output", action="store_true")
    p.add_argument("--timeout", type=int)
    p.add_argument("--allow-missing-paths", action="store_true")
    p.add_argument("--report", default="batch-report.json")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "scan-unsupported":
        scan = scan_unsupported(asm_dir=args.asm_dir, out_dir=args.out_dir)
        print_json(scan.to_dict()) if args.json else print(
            f"Genuine ignores: {len(scan.genuine_ignored)}; low func callers: {len(scan.low_func_callers)}"
        )
        return 0
    if args.command == "sync-ignored":
        data = sync_ignored_toml(config=args.config, ignored_files=args.ignored, output=args.output, dry_run=args.dry_run)
        print_json(data) if args.json else print(f"Synced {data['ignored_count']} ignored functions to {data['output']}")
        return 0
    if args.command == "recomp-smoke":
        data = recomp_smoke(
            config=args.config,
            n64recomp=args.n64recomp,
            max_iterations=args.max_iterations,
            ignored_file=args.ignored_file,
            clean_output=args.clean_output,
            timeout=args.timeout,
            allow_missing_paths=args.allow_missing_paths,
            dry_run=args.dry_run,
            report_path=args.report,
        )
        print_json(data) if args.json else print(
            f"Status: {'ok' if data['ok'] else 'failed'}; discovered {len(data['discovered'])}; report {args.report}"
        )
        return 0 if data["ok"] else 1
    if args.command == "init":
        entrypoint = parse_int(args.entrypoint) if args.entrypoint else None
        out = create_config(
            args.config,
            entrypoint=entrypoint,
            elf_path=args.elf,
            rom_path=args.rom,
            symbols_file_path=args.symbols,
            output_func_path=args.output_func_path,
            relocatable_sections_path=args.relocatable_sections_path,
            single_file_output=args.single_file_output,
            functions_per_output_file=args.functions_per_output_file,
            recomp_include=args.recomp_include,
            overwrite=args.overwrite,
        )
        print(f"Wrote {out}")
        return 0
    if args.command == "check-config":
        result = validate_config(args.config, allow_missing_paths=args.allow_missing_paths)
        print_json(result.to_dict()) if args.json else print(format_validation(result))
        return 0 if result.ok else 1
    if args.command == "run":
        report = run_recomp(
            args.config,
            n64recomp=args.n64recomp,
            clean_output=args.clean_output,
            timeout=args.timeout,
            allow_missing_paths=args.allow_missing_paths,
        )
        write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print(f"Status: {report['status']}")
            print(f"Report: {args.report}")
            if "output_summary" in report:
                print(format_summary(summarize_output(report["output_summary"]["path"])))
        return 0 if report.get("status") == "ok" else 1
    if args.command == "summarize-output":
        summary = summarize_output(args.path, largest=args.largest)
        print_json(summary.to_dict()) if args.json else print(format_summary(summary))
        return 0 if summary.exists else 1
    if args.command == "batch":
        report = run_batch(
            args.manifest,
            mode=args.mode,
            n64recomp=args.n64recomp,
            clean_output=args.clean_output,
            timeout=args.timeout,
            allow_missing_paths=args.allow_missing_paths,
        )
        write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print(f"Projects: {report['project_count']}")
            print(f"Failures: {report['failed_count']}")
            print(f"Report: {args.report}")
        return 0 if report["ok"] else 1
    raise AssertionError(f"unhandled recomp command: {args.command}")
