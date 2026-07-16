from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .util import atomic_write_text


@dataclass
class CdbProbe:
    path: str | None
    available: bool
    checked_paths: list[str]
    wrappers: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    env_names = ["ProgramFiles", "ProgramFiles(x86)"]
    for env in env_names:
        base = os.environ.get(env)
        if not base:
            continue
        for kit in ("10", "11"):
            for arch in ("x64", "x86", "arm64"):
                candidates.append(Path(base) / "Windows Kits" / kit / "Debuggers" / arch / "cdb.exe")
    return candidates


def discover_cdb(root_path: str | Path = ".") -> CdbProbe:
    checked: list[str] = []
    found = shutil.which("cdb") or shutil.which("cdb.exe")
    if found:
        checked.append(found)
    for candidate in _candidate_paths():
        checked.append(str(candidate))
        if not found and candidate.is_file():
            found = str(candidate)
    root = Path(root_path).resolve()
    wrappers = sorted(str(path.relative_to(root)) for path in root.glob("tools/*cdb*.ps1") if path.is_file()) if root.exists() else []
    return CdbProbe(path=found, available=found is not None, checked_paths=checked, wrappers=wrappers)


def format_cdb_probe(probe: CdbProbe) -> str:
    lines = [f"CDB: {probe.path or 'not found'}"]
    lines.append("Wrappers:")
    lines.extend([f"  {wrapper}" for wrapper in probe.wrappers] or ["  none detected"])
    lines.append("Checked paths:")
    lines.extend([f"  {path}" for path in probe.checked_paths] or ["  PATH only"])
    return "\n".join(lines)


def write_cdb_evidence(
    output_path: str | Path,
    *,
    wrapper: str,
    target: str,
    result: str,
    breakpoints: list[str],
    summary: str,
    overwrite: bool = False,
) -> Path:
    out = Path(output_path)
    if out.exists() and not overwrite:
        raise FileExistsError(f"evidence file already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    allowed = {"HIT", "BYPASS", "ABORT", "INCONCLUSIVE"}
    normalized = result.upper()
    if normalized not in allowed:
        raise ValueError(f"result must be one of {', '.join(sorted(allowed))}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    bp_text = "\n".join(f"- {bp}" for bp in breakpoints) if breakpoints else "- none recorded"
    text = f"""# CDB Trace Evidence

Recorded: {now}
Wrapper script: {wrapper}
Target EXE/PDB/build: {target}
Result: {normalized}

## Breakpoints

{bp_text}

## Summary

{summary.strip()}

## Interpretation discipline

- CDB addresses are host-process addresses unless a project wrapper explicitly maps guest PC values.
- A host breakpoint hit proves host execution, not a matching decomp boundary by itself.
- Fix TOML, symbols, overlays, or runtime glue before editing generated recompilation output.
"""
    atomic_write_text(out, text)
    return out
