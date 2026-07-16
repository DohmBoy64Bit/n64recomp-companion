from __future__ import annotations

import argparse

from ..doctor import doctor, format_doctor
from ..toolchain import discover_mips_toolchains, format_toolchains, smoke_test_mips_toolchain
from ..util import parse_int, print_json
from .common import add_json

COMMANDS = {"doctor", "toolchain-info", "mips-smoke"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("doctor", help="check local, Windows, Podman, Splat, CDB, and MIPS tool availability")
    p.add_argument("--n64recomp", help="path to N64Recomp binary")
    p.add_argument("--root", default=".", help="project root used to discover CDB wrappers")
    add_json(p)

    p = sub.add_parser("toolchain-info", help="discover open MIPS cross toolchains")
    p.add_argument("--prefix", help="probe only this prefix, such as mips-linux-gnu-")
    add_json(p)

    p = sub.add_parser("mips-smoke", help="assemble and link a tiny MIPS ELF with the discovered toolchain")
    p.add_argument("--prefix", help="toolchain prefix, such as mips-linux-gnu-")
    p.add_argument("--output-dir", default="build/mips-smoke")
    p.add_argument("--vram", default="0x80000400")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "doctor":
        data = doctor(n64recomp=args.n64recomp, root=args.root)
        print_json(data) if args.json else print(format_doctor(data))
        return 0 if data["n64recomp"]["available"] else 2
    if args.command == "toolchain-info":
        probes = discover_mips_toolchains([args.prefix] if args.prefix else None)
        data = [probe.to_dict() for probe in probes]
        print_json(data) if args.json else print(format_toolchains(probes))
        return 0 if any(probe.usable_for_elf_smoke for probe in probes) else 2
    if args.command == "mips-smoke":
        report = smoke_test_mips_toolchain(output_dir=args.output_dir, prefix=args.prefix, vram=parse_int(args.vram))
        if args.json:
            print_json(report)
        else:
            print(f"Status: {'ok' if report['ok'] else 'failed'}")
            print(f"Prefix: {report['prefix']}")
            print(f"Stage : {report['stage']}")
            print(f"ELF   : {report['paths']['elf']}")
        return 0 if report["ok"] else 1
    raise AssertionError(f"unhandled environment command: {args.command}")
