from __future__ import annotations

import json
import os
import shlex
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .elf import inspect_elf
from .toolchain import choose_toolchain
from .util import atomic_write_text, run_command, safe_rmtree

ASM_SUFFIXES = {".s", ".S"}
C_SUFFIXES = {".c"}
CXX_SUFFIXES = {".cc", ".cpp", ".cxx"}

DEFAULT_ASFLAGS = ["-EB", "-mips3"]
DEFAULT_CFLAGS = [
    "-EB",
    "-mips3",
    "-mabi=32",
    "-G0",
    "-mno-abicalls",
    "-fno-pic",
    "-fno-PIC",
    "-ffreestanding",
    "-fno-builtin",
]
DEFAULT_CXXFLAGS = DEFAULT_CFLAGS + ["-fno-exceptions", "-fno-rtti"]


@dataclass
class ElfBuildPaths:
    root: str
    config: str
    base_path: str
    asm_path: str
    src_path: str | None
    build_path: str
    ld_script_path: str
    elf_path: str
    basename: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ElfBuildReport:
    ok: bool
    dry_run: bool
    profile: str
    prefix: str
    paths: ElfBuildPaths
    object_count: int
    asm_count: int
    c_count: int
    cxx_count: int
    commands: list[list[str]]
    stages: list[dict]
    elf_info: dict | None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["paths"] = self.paths.to_dict()
        return data


def _strip_comment(line: str) -> str:
    in_quote = False
    escaped = False
    out: list[str] = []
    for ch in line:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_quote:
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_quote = not in_quote
            out.append(ch)
            continue
        if ch == "#" and not in_quote:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw[0] in "'\"":
        try:
            return json.loads(raw) if raw[0] == '"' else raw.strip("'")
        except json.JSONDecodeError:
            return raw.strip("'\"")
    return raw


def read_splat_options(config_path: str | Path) -> dict[str, str]:
    cfg = Path(config_path)
    if not cfg.is_file():
        raise FileNotFoundError(f"Splat config not found: {cfg}")
    in_options = False
    options: dict[str, str] = {}
    for raw_line in cfg.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        line = _strip_comment(raw_line)
        if not line.strip():
            continue
        if line.startswith("options:"):
            in_options = True
            continue
        if in_options and line and not line.startswith((" ", "\t")):
            break
        if not in_options or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key and value.strip():
            options[key] = _parse_scalar(value)
    return options


def _resolve_path(base: Path, value: str | None, *, fallback: Path | None = None) -> Path:
    if value:
        value_path = Path(value)
        if value_path.is_absolute():
            return value_path.resolve()
        return (base / value_path).resolve()
    if fallback is None:
        raise ValueError("missing required path")
    return fallback.resolve()


def _resolve_splat_child(
    *,
    base: Path,
    config_dir: Path,
    root: Path,
    value: str | None,
    fallback: Path,
    base_value: str | None,
) -> Path:
    """Resolve a Splat child option relative to base_path.

    Current Splat semantics make child paths relative to ``base_path``.  Older
    versions of this companion generated values that repeated the base prefix
    (for example ``base_path: decomp`` plus ``asm_path: decomp/asm``).  The
    compatibility branch below accepts that layout without changing the
    canonical resolution used for current configs.
    """
    if not value:
        return fallback.resolve()
    child = Path(value)
    if child.is_absolute():
        return child.resolve()
    canonical = (base / child).resolve()
    if canonical.exists():
        return canonical

    base_rel = Path(base_value) if base_value else Path(".")
    if base_value and base_rel.parts and child.parts[: len(base_rel.parts)] == base_rel.parts:
        legacy = (config_dir / child).resolve()
        root_legacy = (root / child).resolve()
        if root_legacy.exists() or (root / child.parent).exists():
            return root_legacy
        return legacy

    root_relative = (root / child).resolve()
    if root_relative.exists() or (child.parts and child.parts[0] == config_dir.name and (root / child.parent).exists()):
        return root_relative

    return canonical


def load_elf_build_paths(config_path: str | Path, *, root_path: str | Path = ".") -> ElfBuildPaths:
    root = Path(root_path).resolve()
    cfg = Path(config_path)
    if not cfg.is_absolute():
        cfg = (root / cfg).resolve()
    options = read_splat_options(cfg)
    basename = options.get("basename") or cfg.stem
    base_value = options.get("base_path")
    canonical_base = _resolve_path(cfg.parent, base_value, fallback=cfg.parent)
    if base_value and not canonical_base.exists():
        root_base = _resolve_path(root, base_value)
        base = root_base if root_base.exists() else canonical_base
    else:
        base = canonical_base
    resolver = lambda value, fallback: _resolve_splat_child(
        base=base,
        config_dir=cfg.parent,
        root=root,
        value=value,
        fallback=fallback,
        base_value=base_value,
    )
    asm = resolver(options.get("asm_path"), base / "asm")
    src = resolver(options.get("src_path"), base / "src") if options.get("src_path") else None
    build = resolver(options.get("build_path"), base / "build")
    ld_script = resolver(options.get("ld_script_path"), base / f"{basename}.ld")
    elf = resolver(options.get("elf_path"), build / f"{basename}.elf")
    return ElfBuildPaths(
        root=str(root),
        config=str(cfg),
        base_path=str(base),
        asm_path=str(asm),
        src_path=str(src) if src else None,
        build_path=str(build),
        ld_script_path=str(ld_script),
        elf_path=str(elf),
        basename=basename,
    )


def _safe_rel(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return Path(path.name)


def _sources(root: Path, paths: ElfBuildPaths, profile: str) -> tuple[list[Path], list[Path], list[Path]]:
    asm_dir = Path(paths.asm_path)
    src_dir = Path(paths.src_path) if paths.src_path else None
    asm_sources = sorted(p for p in asm_dir.rglob("*") if p.is_file() and p.suffix in ASM_SUFFIXES) if asm_dir.is_dir() else []
    if profile == "asm-only" or not src_dir or not src_dir.is_dir():
        return asm_sources, [], []
    c_sources = sorted(p for p in src_dir.rglob("*") if p.is_file() and p.suffix in C_SUFFIXES)
    cxx_sources = sorted(p for p in src_dir.rglob("*") if p.is_file() and p.suffix in CXX_SUFFIXES)
    return asm_sources, c_sources, cxx_sources


def _split_flags(flags: list[str] | None) -> list[str]:
    if not flags:
        return []
    result: list[str] = []
    for flag in flags:
        result.extend(shlex.split(flag))
    return result


def _object_path(source: Path, root: Path, build: Path) -> Path:
    rel = _safe_rel(source, root)
    return (build / rel).with_suffix(".o")


def _tool_path(tools: dict[str, str | None], name: str, prefix: str) -> str:
    return tools.get(name) or f"{prefix}{name}"


def build_elf_from_splat(
    config_path: str | Path,
    *,
    root_path: str | Path = ".",
    prefix: str | None = None,
    profile: str = "asm-only",
    dry_run: bool = False,
    clean: bool = False,
    timeout: int | None = None,
    extra_asflags: list[str] | None = None,
    extra_cflags: list[str] | None = None,
    extra_ldflags: list[str] | None = None,
) -> ElfBuildReport:
    if profile not in {"asm-only", "gnu-c"}:
        raise ValueError("profile must be 'asm-only' or 'gnu-c'")
    paths = load_elf_build_paths(config_path, root_path=root_path)
    root = Path(paths.root)
    build = Path(paths.build_path)
    elf = Path(paths.elf_path)
    ld_script = Path(paths.ld_script_path)
    asm_sources, c_sources, cxx_sources = _sources(root, paths, profile)
    if not asm_sources and not c_sources and not cxx_sources:
        raise FileNotFoundError(f"no assembly or source files were found under {paths.asm_path} or {paths.src_path}")
    if not ld_script.is_file() and not dry_run:
        raise FileNotFoundError(f"linker script not found: {ld_script}")

    probe = choose_toolchain(prefix)
    chosen_prefix = prefix or (probe.prefix if probe else "mips-linux-gnu-")
    tools = {tool.name: tool.path for tool in probe.tools} if probe else {}
    as_tool = _tool_path(tools, "as", chosen_prefix)
    ld_tool = _tool_path(tools, "ld", chosen_prefix)
    gcc_tool = _tool_path(tools, "gcc", chosen_prefix)
    gxx_tool = _tool_path(tools, "g++", chosen_prefix)

    if not dry_run:
        if not probe or not probe.usable_for_elf_smoke:
            raise RuntimeError(f"toolchain prefix {chosen_prefix!r} is missing required as, ld, or readelf")
        if profile == "gnu-c" and c_sources and not tools.get("gcc"):
            raise RuntimeError(f"profile 'gnu-c' requires {chosen_prefix}gcc for C sources")
        if profile == "gnu-c" and cxx_sources and not tools.get("g++"):
            raise RuntimeError(f"profile 'gnu-c' requires {chosen_prefix}g++ for C++ sources")
        if clean and build.exists():
            safe_rmtree(build, protected=[root, Path.home()])
        build.mkdir(parents=True, exist_ok=True)
        elf.parent.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    stages: list[dict] = []
    objects: list[Path] = []
    asflags = DEFAULT_ASFLAGS + _split_flags(extra_asflags)
    cflags = DEFAULT_CFLAGS + _split_flags(extra_cflags)
    cxxflags = DEFAULT_CXXFLAGS + _split_flags(extra_cflags)

    for source in asm_sources:
        obj = _object_path(source, root, build)
        objects.append(obj)
        cmd = [as_tool, *asflags, "-o", str(obj), str(source)]
        commands.append(cmd)
        if not dry_run:
            obj.parent.mkdir(parents=True, exist_ok=True)
            result = run_command(cmd, cwd=root, timeout=timeout)
            stages.append({"stage": "assemble", "source": str(source), **result.to_dict()})
            if result.returncode != 0:
                return ElfBuildReport(False, dry_run, profile, chosen_prefix, paths, len(objects), len(asm_sources), len(c_sources), len(cxx_sources), commands, stages, None)

    for source in c_sources:
        obj = _object_path(source, root, build)
        objects.append(obj)
        cmd = [gcc_tool, *cflags, "-c", "-o", str(obj), str(source)]
        commands.append(cmd)
        if not dry_run:
            obj.parent.mkdir(parents=True, exist_ok=True)
            result = run_command(cmd, cwd=root, timeout=timeout)
            stages.append({"stage": "compile-c", "source": str(source), **result.to_dict()})
            if result.returncode != 0:
                return ElfBuildReport(False, dry_run, profile, chosen_prefix, paths, len(objects), len(asm_sources), len(c_sources), len(cxx_sources), commands, stages, None)

    for source in cxx_sources:
        obj = _object_path(source, root, build)
        objects.append(obj)
        cmd = [gxx_tool, *cxxflags, "-c", "-o", str(obj), str(source)]
        commands.append(cmd)
        if not dry_run:
            obj.parent.mkdir(parents=True, exist_ok=True)
            result = run_command(cmd, cwd=root, timeout=timeout)
            stages.append({"stage": "compile-cxx", "source": str(source), **result.to_dict()})
            if result.returncode != 0:
                return ElfBuildReport(False, dry_run, profile, chosen_prefix, paths, len(objects), len(asm_sources), len(c_sources), len(cxx_sources), commands, stages, None)

    map_path = elf.with_suffix(".map")
    link_cmd = [ld_tool, "-T", str(ld_script), "-Map", str(map_path), "-o", str(elf), *[str(obj) for obj in objects], *(extra_ldflags or [])]
    commands.append(link_cmd)
    if dry_run:
        return ElfBuildReport(True, dry_run, profile, chosen_prefix, paths, len(objects), len(asm_sources), len(c_sources), len(cxx_sources), commands, stages, None)

    link_result = run_command(link_cmd, cwd=root, timeout=timeout)
    stages.append({"stage": "link", **link_result.to_dict()})
    if link_result.returncode != 0:
        return ElfBuildReport(False, dry_run, profile, chosen_prefix, paths, len(objects), len(asm_sources), len(c_sources), len(cxx_sources), commands, stages, None)

    elf_info = inspect_elf(elf).to_dict()
    ok = bool(
        elf_info.get("elf_class") == "ELF32"
        and elf_info.get("endian") == "big"
        and elf_info.get("machine") == "MIPS"
    )
    return ElfBuildReport(ok, dry_run, profile, chosen_prefix, paths, len(objects), len(asm_sources), len(c_sources), len(cxx_sources), commands, stages, elf_info)


POWERSHELL_TEMPLATE = r'''[CmdletBinding()]
param(
  [string]$Config = 'decomp\splat.yaml',
  [string]$Root = '.',
  [string]$Prefix = '',
  [ValidateSet('asm-only','gnu-c')]
  [string]$Profile = 'asm-only',
  [switch]$Clean,
  [switch]$DryRun,
  [string]$Report = 'build\elf-build-report.json'
)

$ErrorActionPreference = 'Stop'
$argsList = @('build-elf', '--config', $Config, '--root', $Root, '--profile', $Profile, '--report', $Report)
if ($Prefix -ne '') { $argsList += @('--prefix', $Prefix) }
if ($Clean) { $argsList += '--clean' }
if ($DryRun) { $argsList += '--dry-run' }
python -m n64recomp_kit @argsList
'''

PYTHON_WRAPPER_TEMPLATE = r'''#!/usr/bin/env python3
from n64recomp_kit.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["build-elf", *(__import__("sys").argv[1:])]))
'''


def emit_elf_build_helpers(root_path: str | Path = ".", *, overwrite: bool = False) -> dict:
    root = Path(root_path).resolve()
    scripts = root / "scripts"
    tools = root / "tools"
    scripts.mkdir(parents=True, exist_ok=True)
    tools.mkdir(parents=True, exist_ok=True)
    outputs = [scripts / "Build-N64Elf.ps1", tools / "n64_build_elf.py"]
    for output in outputs:
        if output.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing helper: {output}")
    atomic_write_text(outputs[0], POWERSHELL_TEMPLATE)
    atomic_write_text(outputs[1], PYTHON_WRAPPER_TEMPLATE)
    try:
        outputs[1].chmod(outputs[1].stat().st_mode | 0o111)
    except OSError:
        pass
    return {"ok": True, "root": str(root), "files": [str(path) for path in outputs]}
