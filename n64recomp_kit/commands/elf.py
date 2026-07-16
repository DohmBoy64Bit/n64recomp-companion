from __future__ import annotations

import argparse

from ..audit import elf_symbol_audit, export_functions, filter_ignored_by_export
from ..elf import format_elf_info, inspect_elf
from ..elf_build import build_elf_from_splat, emit_elf_build_helpers
from ..splat_repair import mips_link_preflight
from ..util import print_json, write_json
from .common import add_json

COMMANDS = {
    "elf-info",
    "emit-elf-build",
    "build-elf",
    "elf-symbol-audit",
    "export-functions",
    "filter-ignored",
    "mips-link-preflight",
}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("elf-info", help="inspect an ELF32 file")
    p.add_argument("elf")
    add_json(p)

    p = sub.add_parser("emit-elf-build", help="write Windows/Python helper scripts for building the Splat ELF")
    p.add_argument("--root", default=".")
    p.add_argument("--overwrite", action="store_true")
    add_json(p)

    p = sub.add_parser("build-elf", help="assemble/link Splat output into the ELF consumed by N64Recomp")
    p.add_argument("--config", required=True, help="Splat YAML config with elf_path and ld_script_path")
    p.add_argument("--root", default=".", help="project root used to resolve relative Splat paths")
    p.add_argument("--prefix", help="MIPS toolchain prefix, such as mips-linux-gnu-")
    p.add_argument("--profile", choices=["asm-only", "gnu-c"], default="asm-only")
    p.add_argument("--clean", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout", type=int)
    p.add_argument("--report", default="elf-build-report.json")
    p.add_argument("--asflag", action="append", default=[], help="extra assembler flag; may be repeated")
    p.add_argument("--cflag", action="append", default=[], help="extra C/C++ compiler flag; may be repeated")
    p.add_argument("--ldflag", action="append", default=[], help="extra linker flag; may be repeated")
    add_json(p)

    p = sub.add_parser("elf-symbol-audit", help="audit ELF/readelf symbols for N64Recomp readiness")
    p.add_argument("--elf", help="ELF to inspect with mips-linux-gnu-readelf -sW")
    p.add_argument("--symbols-file", help="saved readelf -sW output for offline auditing")
    p.add_argument("--readelf", help="explicit readelf executable")
    p.add_argument("--prefix", help="toolchain prefix, default mips-linux-gnu-")
    p.add_argument("--report", help="optional JSON report path")
    p.add_argument("--alias-policy", choices=["allow", "warn", "error"], default="allow")
    add_json(p)

    p = sub.add_parser("export-functions", help="export sized FUNC symbols for N64Recomp workflows")
    p.add_argument("--elf", help="ELF to inspect with readelf")
    p.add_argument("--symbols-file", help="saved readelf -sW output")
    p.add_argument("--out-dir", default="symbols/recomp")
    p.add_argument("--readelf", help="explicit readelf executable")
    p.add_argument("--prefix", help="toolchain prefix, default mips-linux-gnu-")
    p.add_argument("--range", action="append", default=[], help="region range name:start:end; may be repeated")
    add_json(p)

    p = sub.add_parser("filter-ignored", help="drop ignored function names that are not sized ELF functions")
    p.add_argument("--sized-tsv", required=True)
    p.add_argument("--ignored", action="append", required=True, help="ignored list file; may be repeated")
    p.add_argument("--dry-run", action="store_true")
    add_json(p)

    p = sub.add_parser("mips-link-preflight", help="dry-run or execute the MIPS asm/link path from Splat YAML")
    p.add_argument("--config", required=True)
    p.add_argument("--root", default=".")
    p.add_argument("--prefix")
    p.add_argument("--profile", choices=["asm-only", "gnu-c"], default="asm-only")
    p.add_argument("--timeout", type=int)
    p.add_argument("--execute", action="store_true", help="actually assemble/link instead of dry-run")
    p.add_argument("--report")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "elf-info":
        info = inspect_elf(args.elf)
        print_json(info.to_dict()) if args.json else print(format_elf_info(info))
        return 0
    if args.command == "emit-elf-build":
        report = emit_elf_build_helpers(args.root, overwrite=args.overwrite)
        if args.json:
            print_json(report)
        else:
            print("Wrote ELF build helpers:")
            for path in report["files"]:
                print(f"  {path}")
        return 0
    if args.command == "build-elf":
        report = build_elf_from_splat(
            args.config,
            root_path=args.root,
            prefix=args.prefix,
            profile=args.profile,
            dry_run=args.dry_run,
            clean=args.clean,
            timeout=args.timeout,
            extra_asflags=args.asflag,
            extra_cflags=args.cflag,
            extra_ldflags=args.ldflag,
        ).to_dict()
        write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print(f"Status: {'ok' if report['ok'] else 'failed'}")
            print(f"Dry run: {report['dry_run']}")
            print(f"ELF    : {report['paths']['elf_path']}")
            print(f"Objects: {report['object_count']}")
            print(f"Report : {args.report}")
        return 0 if report["ok"] else 1
    if args.command == "elf-symbol-audit":
        data = elf_symbol_audit(
            elf=args.elf,
            symbols_file=args.symbols_file,
            readelf=args.readelf,
            prefix=args.prefix,
            alias_policy=args.alias_policy,
        )
        if args.report:
            write_json(args.report, data)
        if args.json:
            print_json(data)
        else:
            print(f"Status: {'ok' if data['ok'] else 'issues'}")
            print(f"Functions: {data['function_count']} ({data['sized_function_count']} sized)")
            print(f"Issues: {data['issue_count']}")
        return 0 if data["ok"] else 1
    if args.command == "export-functions":
        data = export_functions(
            elf=args.elf,
            symbols_file=args.symbols_file,
            out_dir=args.out_dir,
            readelf=args.readelf,
            prefix=args.prefix,
            ranges=args.range,
        )
        print_json(data) if args.json else print(f"Exported {data['exported_functions']} functions to {data['out_dir']}")
        return 0
    if args.command == "filter-ignored":
        data = filter_ignored_by_export(sized_tsv=args.sized_tsv, ignored_files=args.ignored, dry_run=args.dry_run)
        print_json(data) if args.json else print(f"Dropped {data['total_dropped']} ignored entries not present as sized ELF functions")
        return 0
    if args.command == "mips-link-preflight":
        data = mips_link_preflight(
            config=args.config,
            root=args.root,
            prefix=args.prefix,
            profile=args.profile,
            timeout=args.timeout,
            dry_run=not args.execute,
            report=args.report,
        )
        print_json(data) if args.json else print(f"Status: {'ok' if data['ok'] else 'failed'}; dry_run {data['dry_run']}")
        return 0 if data["ok"] else 1
    raise AssertionError(f"unhandled ELF command: {args.command}")
