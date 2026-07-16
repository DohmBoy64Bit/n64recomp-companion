from __future__ import annotations

import argparse

from ..rom import convert_to_z64, format_rom_info, inspect_rom
from ..rom_match import rom_build_from_map, rom_match_check, rom_match_sections
from ..util import parse_int, print_json
from .common import add_json

COMMANDS = {"rom-info", "convert-rom", "rom-match-check", "rom-match-sections", "rom-build-from-map"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("rom-info", help="inspect an N64 ROM header")
    p.add_argument("rom")
    add_json(p)

    p = sub.add_parser("convert-rom", help="convert .n64/.v64 byte order to .z64")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--overwrite", action="store_true")
    add_json(p)

    p = sub.add_parser("rom-match-check", help="compare an expected ROM/image against an actual rebuilt ROM/image")
    p.add_argument("--expected", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--start", default="0")
    p.add_argument("--size")
    p.add_argument("--report")
    add_json(p)

    p = sub.add_parser("rom-match-sections", help="compare section ranges from a JSON manifest")
    p.add_argument("--manifest", required=True)
    p.add_argument("--report")
    add_json(p)

    p = sub.add_parser("rom-build-from-map", help="build a ROM/image from a simple offset size source map")
    p.add_argument("--map", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--root", help="base directory for map sources; defaults to the map file directory")
    p.add_argument("--fill", default="0")
    p.add_argument("--size")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "rom-info":
        info = inspect_rom(args.rom)
        print_json(info.to_dict()) if args.json else print(format_rom_info(info))
        return 0
    if args.command == "convert-rom":
        data = convert_to_z64(args.input, args.output, overwrite=args.overwrite)
        print_json(data) if args.json else print(f"Wrote {data['output']} ({data['source_byte_order']} -> z64-big-endian)")
        return 0
    if args.command == "rom-match-check":
        data = rom_match_check(
            expected=args.expected,
            actual=args.actual,
            start=parse_int(args.start),
            size=parse_int(args.size) if args.size else None,
            report=args.report,
        )
        print_json(data) if args.json else print(f"Status: {'match' if data['ok'] else 'mismatch'}")
        return 0 if data["ok"] else 1
    if args.command == "rom-match-sections":
        data = rom_match_sections(manifest=args.manifest, report=args.report)
        print_json(data) if args.json else print(f"Status: {'match' if data['ok'] else 'mismatch'}; sections {data['section_count']}")
        return 0 if data["ok"] else 1
    if args.command == "rom-build-from-map":
        data = rom_build_from_map(
            map_file=args.map,
            output=args.output,
            root=args.root,
            fill=parse_int(args.fill),
            size=parse_int(args.size) if args.size else None,
            dry_run=args.dry_run,
            report=args.report,
        )
        print_json(data) if args.json else print(f"Status: {'ok' if data['ok'] else 'failed'}; output {data['output']}")
        return 0 if data["ok"] else 1
    raise AssertionError(f"unhandled ROM command: {args.command}")
