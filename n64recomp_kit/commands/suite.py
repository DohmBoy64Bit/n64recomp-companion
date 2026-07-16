from __future__ import annotations

import argparse

from ..real_rom_suite import EXECUTION_STAGES, format_real_rom_suite, run_real_rom_suite
from ..util import parse_int, print_json
from .common import add_json

COMMANDS = {"real-rom-test"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("real-rom-test", help="run a local evidence-producing test suite against a real ROM and optional project artifacts")
    p.add_argument("--rom", required=True, help="legally obtained .z64, .v64, or .n64 ROM")
    p.add_argument("--project-root", default=".")
    p.add_argument("--source-root", help="companion source tree used for unit tests, release verification, and Podman")
    p.add_argument("--output", default="build/real-rom-test")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--strict", action="store_true", help="fail when a requested external stage is blocked")
    p.add_argument(
        "--execute",
        action="append",
        choices=sorted(EXECUTION_STAGES | {"all"}),
        default=[],
        help="external stage to execute; may be repeated; default performs non-destructive local checks only",
    )
    p.add_argument("--code-start", default="0x1000", help="ROM offset for the generated Splat starting config")
    p.add_argument("--vram", default="0x80000400", help="VRAM start for generated smoke artifacts")
    p.add_argument("--splat-config")
    p.add_argument("--allow-generated-splat", action="store_true", help="allow Splat to run on the broad generated starting config")
    p.add_argument("--elf")
    p.add_argument("--recomp-config")
    p.add_argument("--n64recomp")
    p.add_argument("--matching-root")
    p.add_argument("--runtime-project")
    p.add_argument("--mips-prefix")
    p.add_argument("--mupen-root")
    p.add_argument("--provider", choices=["lmstudio", "llama-cpp"], default="lmstudio")
    p.add_argument("--model")
    p.add_argument("--base-url")
    p.add_argument("--api-key", default="local")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--podman-image", default="n64recomp-companion:real-rom-test")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    report = run_real_rom_suite(
        rom=args.rom,
        output_dir=args.output,
        project_root=args.project_root,
        source_root=args.source_root,
        execute=args.execute,
        strict=args.strict,
        overwrite=args.overwrite,
        code_start=parse_int(args.code_start),
        vram=parse_int(args.vram),
        splat_config=args.splat_config,
        allow_generated_splat=args.allow_generated_splat,
        elf=args.elf,
        recomp_config=args.recomp_config,
        n64recomp=args.n64recomp,
        matching_root=args.matching_root,
        runtime_project=args.runtime_project,
        mips_prefix=args.mips_prefix,
        mupen_root=args.mupen_root,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        timeout=args.timeout,
        podman_image=args.podman_image,
    )
    print_json(report.to_dict()) if args.json else print(format_real_rom_suite(report))
    return 0 if report.ok else 1
