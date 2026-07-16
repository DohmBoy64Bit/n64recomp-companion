from __future__ import annotations

import os
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import validate_config
from .util import run_command, safe_rmtree


@dataclass
class OutputSummary:
    path: str
    exists: bool
    c_files: int
    cpp_files: int
    header_files: int
    other_files: int
    total_files: int
    total_bytes: int
    largest_files: list[dict[str, Any]]

    def to_dict(self) -> dict:
        return asdict(self)


def summarize_output(path: str | Path, *, largest: int = 10) -> OutputSummary:
    p = Path(path)
    if not p.exists():
        return OutputSummary(str(p), False, 0, 0, 0, 0, 0, 0, [])
    c_files = cpp_files = header_files = other_files = total_files = total_bytes = 0
    sizes: list[tuple[int, Path]] = []
    for child in p.rglob("*"):
        if not child.is_file():
            continue
        total_files += 1
        size = child.stat().st_size
        total_bytes += size
        sizes.append((size, child))
        suffix = child.suffix.lower()
        if suffix == ".c":
            c_files += 1
        elif suffix in {".cc", ".cpp", ".cxx"}:
            cpp_files += 1
        elif suffix in {".h", ".hpp", ".hh", ".hxx", ".inl"}:
            header_files += 1
        else:
            other_files += 1
    sizes.sort(reverse=True, key=lambda item: item[0])
    largest_files = [
        {"path": str(file.relative_to(p)), "bytes": size}
        for size, file in sizes[:largest]
    ]
    return OutputSummary(str(p), True, c_files, cpp_files, header_files, other_files, total_files, total_bytes, largest_files)


def format_summary(summary: OutputSummary) -> str:
    if not summary.exists:
        return f"Output path does not exist: {summary.path}"
    lines = [
        f"Output path : {summary.path}",
        f"Total files : {summary.total_files}",
        f"Total bytes : {summary.total_bytes}",
        f"C files     : {summary.c_files}",
        f"C++ files   : {summary.cpp_files}",
        f"Headers     : {summary.header_files}",
        f"Other files : {summary.other_files}",
    ]
    if summary.largest_files:
        lines.append("Largest files:")
        for entry in summary.largest_files:
            lines.append(f"  {entry['bytes']:>10}  {entry['path']}")
    return "\n".join(lines)


def find_n64recomp(explicit: str | None = None) -> str | None:
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(["N64Recomp", "N64Recomp.exe"])
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return str(path.resolve())
        found = shutil.which(candidate)
        if found:
            return found
    return None


def run_recomp(
    config_path: str | Path,
    *,
    n64recomp: str | None = None,
    clean_output: bool = False,
    timeout: int | None = None,
    allow_missing_paths: bool = False,
) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    validation = validate_config(config_path, allow_missing_paths=allow_missing_paths)
    binary = find_n64recomp(n64recomp)
    report: dict[str, Any] = {
        "config": str(config_path),
        "validation": validation.to_dict(),
        "n64recomp": binary,
        "started_at_unix": int(time.time()),
    }
    if not validation.ok:
        report["status"] = "validation_failed"
        return report
    if binary is None:
        report["status"] = "missing_n64recomp_binary"
        return report
    out_path_value = validation.resolved_paths.get("input.output_func_path")
    if out_path_value:
        out_path = Path(out_path_value)
        if clean_output and out_path.exists():
            safe_rmtree(out_path, protected=[config_path.parent, Path.home()])
        out_path.mkdir(parents=True, exist_ok=True)
    else:
        out_path = None
    result = run_command([binary, config_path.name], cwd=config_path.parent, timeout=timeout)
    report["command"] = result.to_dict()
    report["status"] = "ok" if result.returncode == 0 else "failed"
    if out_path is not None:
        report["output_summary"] = summarize_output(out_path).to_dict()
    return report
