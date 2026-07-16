from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .util import atomic_write_text

ROM_EXTENSIONS = {".z64", ".n64", ".v64"}
ELF_EXTENSIONS = {".elf"}
YAML_EXTENSIONS = {".yaml", ".yml"}
SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "venv", ".deps", "node_modules", "__pycache__", "packages", "installed", "_deps"}


@dataclass
class WorkspaceScan:
    root: str
    state_file: str | None
    roms: list[str] = field(default_factory=list)
    splat_yamls: list[str] = field(default_factory=list)
    elfs: list[str] = field(default_factory=list)
    has_asm_dir: bool = False
    has_configure_py: bool = False
    has_build_dir: bool = False
    recomp_tomls: list[str] = field(default_factory=list)
    has_recompiled_funcs: bool = False
    has_external_n64recomp: bool = False
    has_external_runtime: bool = False
    has_function_ledger: bool = False
    cdb_wrappers: list[str] = field(default_factory=list)
    track: str = "unknown"
    phase: str = "unclassified"
    gaps: list[str] = field(default_factory=list)
    next_step: str = "Run workspace-status again from the project root after adding game files."

    def to_dict(self) -> dict:
        return asdict(self)


def _is_under_skipped_dir(path: Path, root: Path, skip_dirs: set[str] | None = None) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    ignored = skip_dirs or SKIP_DIRS
    return any(part in ignored for part in parts[:-1])


def _limited_files(root: Path, max_depth: int = 4, skip_dirs: set[str] | None = None) -> Iterable[Path]:
    root = root.resolve()
    ignored = skip_dirs or SKIP_DIRS
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        dirs[:] = [d for d in dirs if d not in ignored and depth < max_depth]
        for name in files:
            yield current_path / name


def _rel_list(paths: Iterable[Path], root: Path) -> list[str]:
    out: list[str] = []
    for p in sorted(set(path.resolve() for path in paths)):
        try:
            out.append(str(p.relative_to(root)))
        except ValueError:
            out.append(str(p))
    return out


def _looks_like_recomp_toml(path: Path) -> bool:
    if path.name.endswith(".recomp.toml"):
        return True
    if path.suffix != ".toml":
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    return "[input]" in head and ("output_func_path" in head or "elf_path" in head or "symbols_file_path" in head)


def scan_workspace(root_path: str | Path = ".", *, ignore_dirs: Iterable[str] = (), max_depth: int = 4) -> WorkspaceScan:
    root = Path(root_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"workspace root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"workspace root is not a directory: {root}")

    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")
    skip_dirs = set(SKIP_DIRS) | {item for item in ignore_dirs if item}
    files = list(_limited_files(root, max_depth=max_depth, skip_dirs=skip_dirs))
    roms = [p for p in files if p.suffix.lower() in ROM_EXTENSIONS]
    yamls = [p for p in files if p.suffix.lower() in YAML_EXTENSIONS and not _is_under_skipped_dir(p, root, skip_dirs)]
    elfs = [p for p in files if p.suffix.lower() in ELF_EXTENSIONS and not _is_under_skipped_dir(p, root, skip_dirs)]
    tomls = [p for p in files if _looks_like_recomp_toml(p)]
    tools_dir = root / "tools"
    cdb = sorted(tools_dir.glob("*cdb*.ps1")) if tools_dir.is_dir() else []

    scan = WorkspaceScan(
        root=str(root),
        state_file=str(root / "N64_PROJECT_STATE.md") if (root / "N64_PROJECT_STATE.md").exists() else None,
        roms=_rel_list(roms, root),
        splat_yamls=_rel_list(yamls, root),
        elfs=_rel_list(elfs, root),
        has_asm_dir=(root / "asm").is_dir() or any((root / part).is_dir() for part in ("src/asm", "decomp/asm")),
        has_configure_py=(root / "configure.py").is_file(),
        has_build_dir=(root / "build").is_dir(),
        recomp_tomls=_rel_list(tomls, root),
        has_recompiled_funcs=(root / "RecompiledFuncs").is_dir() or any(
            path.name == "RecompiledFuncs" and path.is_dir()
            for path in {file.parent for file in files}
        ),
        has_external_n64recomp=(root / "external" / "N64Recomp").exists() or (root / ".deps" / "N64Recomp").exists(),
        has_external_runtime=any(
            candidate.exists()
            for candidate in (
                root / "external" / "N64ModernRuntime",
                root / "external" / "RT64",
                root / "runtime",
                root / "host",
                root / ".n64recomp-runtime",
            )
        ) or any(path.name == ".n64recomp-runtime" for path in files),
        has_function_ledger=(root / "docs" / "function_ledger.md").is_file(),
        cdb_wrappers=_rel_list(cdb, root),
    )
    _classify(scan)
    return scan


def _classify(scan: WorkspaceScan) -> None:
    has_rom = bool(scan.roms)
    has_yaml = bool(scan.splat_yamls)
    has_recomp = bool(scan.recomp_tomls or scan.has_recompiled_funcs or scan.has_external_n64recomp)
    has_matching = bool(has_yaml or scan.has_asm_dir or scan.has_configure_py)

    if has_recomp:
        scan.track = "Track B - N64Recomp static port"
        if not has_yaml and not scan.has_function_ledger:
            scan.phase = "B0 - metadata discovery"
            scan.gaps.append("No splat YAML or function ledger found near the project root.")
            scan.next_step = "Record clean ROM/symbol/overlay evidence before relying on codegen output."
        elif scan.recomp_tomls and not scan.has_recompiled_funcs:
            scan.phase = "B1 - code generation setup"
            scan.next_step = "Validate the recomp TOML, inspect the input ELF, then run N64Recomp and read the report."
        elif scan.has_recompiled_funcs and not scan.has_external_runtime:
            scan.phase = "B2 - runtime integration"
            scan.gaps.append("Generated recompilation output exists, but no N64ModernRuntime or host runtime folder was detected.")
            scan.next_step = "Wire runtime, overlays, DMA, saves, input, audio, and renderer before debugging gameplay."
        else:
            scan.phase = "B3/B4 - host bring-up or polish"
            scan.next_step = "Use CDB traces for host crashes and keep fixes in TOML/runtime code rather than generated RecompiledFuncs."
    elif has_matching:
        scan.track = "Track A - matching decompilation"
        if not scan.has_asm_dir:
            scan.phase = "1 - Splat split setup"
            scan.next_step = "Run Splat split, then verify asm output was generated from the normalized z64 ROM."
        elif not scan.has_configure_py:
            scan.phase = "2 - first assembly-only match setup"
            scan.gaps.append("asm exists but configure.py was not detected.")
            scan.next_step = "Emit or add an assembly-only configure.py, add the linker script, then build and diff."
        elif not scan.elfs:
            scan.phase = "3 - ELF handoff"
            scan.gaps.append("No built ELF was detected near the project root.")
            scan.next_step = "Build the Splat-configured ELF, inspect it, then use it as the N64Recomp input."
        elif not scan.has_function_ledger:
            scan.phase = "4 - discovery preparation"
            scan.gaps.append("No docs/function_ledger.md found.")
            scan.next_step = "Create a function ledger before promoting boundaries into symbol metadata or recomp TOML."
        else:
            scan.phase = "4/5 - discovery or runtime block"
            scan.next_step = "Promote only evidence-backed function boundaries and keep BSS/segment fixes in the Splat YAML."
    elif has_rom:
        scan.track = "Track A - matching decompilation"
        scan.phase = "0 - ROM recon"
        scan.gaps.append("No Splat YAML found yet.")
        scan.next_step = "Inspect ROM byte order/hash, normalize to z64 when needed, then initialize Splat."
    else:
        scan.track = "unknown"
        scan.phase = "unclassified"
        scan.gaps.append("No ROM, Splat YAML, configure.py, recomp TOML, or RecompiledFuncs directory was detected.")
        scan.next_step = "Run from the game/decomp root or provide that root with --root."

    if has_recomp and scan.has_recompiled_funcs:
        scan.gaps.append("Never treat generated RecompiledFuncs as the primary edit target; fix TOML, symbols, overlays, or runtime glue first.")
    if scan.cdb_wrappers and "Track B" in scan.track:
        scan.next_step += " Existing CDB wrappers were detected; read them before changing breakpoints."


def format_workspace_scan(scan: WorkspaceScan) -> str:
    lines = [
        f"Root : {scan.root}",
        f"Track: {scan.track}",
        f"Phase: {scan.phase}",
        f"State: {scan.state_file or 'not found'}",
    ]
    sections = [
        ("ROMs", scan.roms),
        ("Splat YAML", scan.splat_yamls),
        ("ELF", scan.elfs),
        ("Recomp TOML", scan.recomp_tomls),
        ("CDB wrappers", scan.cdb_wrappers),
    ]
    for title, values in sections:
        lines.append(f"{title}:")
        lines.extend([f"  {value}" for value in values] or ["  none detected"])
    lines.extend([
        f"asm/              : {'yes' if scan.has_asm_dir else 'no'}",
        f"configure.py      : {'yes' if scan.has_configure_py else 'no'}",
        f"RecompiledFuncs   : {'yes' if scan.has_recompiled_funcs else 'no'}",
        f"external/N64Recomp: {'yes' if scan.has_external_n64recomp else 'no'}",
        f"runtime folder    : {'yes' if scan.has_external_runtime else 'no'}",
        f"function ledger   : {'yes' if scan.has_function_ledger else 'no'}",
    ])
    if scan.gaps:
        lines.append("Gaps:")
        lines.extend(f"  - {gap}" for gap in scan.gaps)
    lines.append(f"Next: {scan.next_step}")
    return "\n".join(lines)


def init_project_state(root_path: str | Path = ".", *, overwrite: bool = False) -> Path:
    root = Path(root_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    out = root / "N64_PROJECT_STATE.md"
    if out.exists() and not overwrite:
        raise FileExistsError(f"state file already exists: {out}")
    scan = scan_workspace(root)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = f"""# N64 Project State

Last updated: {now}
Project root: {root}
Detected track: {scan.track}
Detected phase: {scan.phase}

## Source files

- ROMs: {', '.join(scan.roms) if scan.roms else 'none recorded'}
- Splat YAML: {', '.join(scan.splat_yamls) if scan.splat_yamls else 'none recorded'}
- Recomp TOML: {', '.join(scan.recomp_tomls) if scan.recomp_tomls else 'none recorded'}
- Function ledger: {'docs/function_ledger.md' if scan.has_function_ledger else 'none recorded'}

## Ground rules

- BSS, segment, overlay, and split fixes belong in Splat YAML or symbol metadata, not in generated asm.
- N64Recomp generated output is an artifact; fix TOML, symbols, overlays, or runtime glue before editing generated code.
- Do not commit ROMs, proprietary game assets, private SDK material, or local absolute ROM paths.
- Claim build, match, or recomp success only after preserving command output or a JSON report.

## Tool versions

Run these commands after setup and paste the output here:

```powershell
python -m n64recomp_kit doctor
python -m n64recomp_kit workspace-status --root .
```

## Crashes and triage

| Date | Track/phase | Evidence file | Result | Next fix layer |
|---|---|---|---|---|

## Decisions

| Date | Decision | Evidence |
|---|---|---|
"""
    atomic_write_text(out, text)
    return out


def init_function_ledger(root_path: str | Path = ".", *, overwrite: bool = False) -> Path:
    root = Path(root_path).resolve()
    out = root / "docs" / "function_ledger.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not overwrite:
        raise FileExistsError(f"function ledger already exists: {out}")
    text = """# Function Ledger

Promote a boundary only after raw disassembly, branch targets, delay slots, data boundaries, and segment or overlay mapping support it.

| Name | VRAM start | VRAM end | Size | ROM/VROM | Type | Confidence | Evidence |
|---|---:|---:|---:|---:|---|---|---|

Confidence labels: Known, Likely, Tentative, Unknown.
"""
    atomic_write_text(out, text)
    return out
