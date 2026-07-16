from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import tomlkit

from .audit import read_names_file, sort_names
from .recomp import run_recomp
from .util import atomic_write_text, backup_file, write_json

UNSUPPORTED_MNEMONICS = frozenset({"trunc.l.d", "trunc.l.s"})
GLABEL_RE = re.compile(r"^\s*(?:glabel|\.globl)\s+([A-Za-z_.$][\w.$]*)")
LABEL_RE = re.compile(r"^\s*([A-Za-z_.$][\w.$]*):\s*(?:#.*)?$")
ENDLABEL_RE = re.compile(r"^\s*endlabel\b")
COP0_RE = re.compile(r"\b(mfc0|mtc0)\s+\$[a-z0-9]+,\s*\$(\d+)", re.IGNORECASE)
JAL_LOW_RE = re.compile(r"\bjal\s+(func_800[0-9A-Fa-f]+)\b", re.IGNORECASE)


@dataclass
class UnsupportedScan:
    ok: bool
    asm_dir: str
    genuine_ignored: list[str]
    low_func_callers: list[str]
    files_scanned: int
    outputs: dict[str, str]

    def to_dict(self) -> dict:
        return asdict(self)


def scan_asm_file(path: Path) -> tuple[set[str], set[str]]:
    unsupported: set[str] = set()
    low_callers: set[str] = set()
    current: str | None = None
    pending_global: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = GLABEL_RE.match(line)
        if match:
            pending_global = match.group(1)
            if line.startswith("glabel"):
                current = pending_global
            continue
        match = LABEL_RE.match(line)
        if match:
            label = match.group(1)
            if label.startswith("func_") or label == pending_global:
                current = label
            continue
        if ENDLABEL_RE.match(line):
            current = None
            continue
        if current is None:
            continue
        lower = line.lower()
        if any(mnemonic in lower for mnemonic in UNSUPPORTED_MNEMONICS):
            unsupported.add(current)
        cop0 = COP0_RE.search(line)
        if cop0 and cop0.group(2) != "12":
            unsupported.add(current)
        if JAL_LOW_RE.search(line):
            low_callers.add(current)
    return unsupported, low_callers


def scan_unsupported(*, asm_dir: str | Path, out_dir: str | Path = "symbols/recomp") -> UnsupportedScan:
    asm = Path(asm_dir)
    if not asm.is_dir():
        raise FileNotFoundError(f"asm dir missing: {asm}")
    unsupported: set[str] = set()
    callers: set[str] = set()
    files = 0
    for path in sorted([*asm.rglob("*.s"), *asm.rglob("*.S")]):
        files += 1
        unsupported_in_file, callers_in_file = scan_asm_file(path)
        unsupported |= unsupported_in_file
        callers |= callers_in_file
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    genuine = sort_names(unsupported)
    low = sort_names(callers - unsupported)
    paths = {
        "ignored_genuine": str(out / "ignored-genuine.txt"),
        "low_func_callers": str(out / "func-800-callers.txt"),
        "legacy_union": str(out / "ignored-funcs.txt"),
    }
    atomic_write_text(
        paths["ignored_genuine"],
        "# Genuinely unsupported instruction functions for [patches].ignored.\n"
        + "\n".join(genuine)
        + ("\n" if genuine else ""),
    )
    atomic_write_text(
        paths["low_func_callers"],
        "# Functions that call func_800* symbols; review mirror/manual function setup before ignoring.\n"
        + "\n".join(low)
        + ("\n" if low else ""),
    )
    union = sort_names(genuine + low)
    atomic_write_text(
        paths["legacy_union"],
        "# Legacy union of genuine ignores and low-memory callers.\n"
        + "\n".join(union)
        + ("\n" if union else ""),
    )
    return UnsupportedScan(True, str(asm), genuine, low, files, paths)


def sync_ignored_toml(*, config: str | Path, ignored_files: Iterable[str | Path], output: str | Path | None = None, dry_run: bool = False) -> dict:
    cfg = Path(config).resolve()
    text = cfg.read_text(encoding="utf-8")
    document = tomlkit.parse(text)
    names: list[str] = []
    patches = document.get("patches")
    if isinstance(patches, dict):
        existing = patches.get("ignored", [])
        if isinstance(existing, list):
            names.extend(str(item) for item in existing if isinstance(item, str) and item)
    for file in ignored_files:
        names.extend(read_names_file(file))
    sorted_names = sort_names(names)
    if patches is None:
        patches = tomlkit.table()
        document["patches"] = patches
    if not isinstance(patches, dict):
        raise ValueError("[patches] must be a TOML table")
    ignored = tomlkit.array().multiline(True)
    for name in sorted_names:
        ignored.append(name)
    patches["ignored"] = ignored
    new_text = tomlkit.dumps(document)
    out = Path(output).resolve() if output else cfg
    changed = new_text != text or out != cfg
    backup = None
    if not dry_run:
        if out == cfg and changed:
            backup_path = backup_file(cfg)
            backup = str(backup_path) if backup_path else None
        atomic_write_text(out, new_text)
    return {
        "ok": True,
        "dry_run": dry_run,
        "config": str(cfg),
        "output": str(out),
        "backup": backup,
        "ignored_count": len(sorted_names),
        "changed": changed,
        "ignored": sorted_names,
    }

def extract_failed_function(text: str) -> str | None:
    patterns = [
        r"(?:function|symbol|func)[:= ]+(func_[0-9A-Fa-f]{6,8})",
        r"\b(func_[0-9A-Fa-f]{6,8})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def recomp_smoke(
    *,
    config: str | Path,
    n64recomp: str | None = None,
    max_iterations: int = 5,
    ignored_file: str | Path | None = None,
    clean_output: bool = False,
    timeout: int | None = None,
    allow_missing_paths: bool = False,
    dry_run: bool = False,
    report_path: str | Path | None = None,
) -> dict:
    if max_iterations <= 0:
        raise ValueError("max_iterations must be greater than zero")
    source_config = Path(config).resolve()
    ignored_path = Path(ignored_file).resolve() if ignored_file else source_config.parent / "ignored-extra.txt"
    discovered: list[str] = []
    iterations: list[dict] = []

    for index in range(max_iterations):
        iteration_config = source_config.parent / f".{source_config.stem}.smoke-{index + 1}.toml"
        sync_ignored_toml(config=source_config, ignored_files=[ignored_path], output=iteration_config)
        try:
            if dry_run:
                iterations.append(
                    {
                        "iteration": index + 1,
                        "status": "dry_run",
                        "source_config": str(source_config),
                        "iteration_config": str(iteration_config),
                        "ignored_count": len(read_names_file(ignored_path)),
                    }
                )
                break
            run_report = run_recomp(
                iteration_config,
                n64recomp=n64recomp,
                clean_output=clean_output and index == 0,
                timeout=timeout,
                allow_missing_paths=allow_missing_paths,
            )
            entry = {
                "iteration": index + 1,
                "status": run_report.get("status"),
                "n64recomp": run_report.get("n64recomp"),
                "iteration_config": str(iteration_config),
            }
            command_report = run_report.get("command") or {}
            output_text = (command_report.get("stdout") or "") + "\n" + (command_report.get("stderr") or "")
            failed = extract_failed_function(output_text)
            if failed:
                entry["failed_function"] = failed
                existing = read_names_file(ignored_path)
                if failed in existing:
                    entry["status"] = "no_progress"
                    entry["reason"] = "the same failed function was already ignored"
                    iterations.append(entry)
                    break
                discovered.append(failed)
                ignored_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(ignored_path, "\n".join(sort_names(existing + [failed])) + "\n")
                entry["next_iteration_ignored_count"] = len(sort_names(existing + [failed]))
            iterations.append(entry)
            if run_report.get("status") == "ok" or not failed:
                break
        finally:
            iteration_config.unlink(missing_ok=True)

    final_status = iterations[-1]["status"] if iterations else "not_run"
    final = {
        "ok": final_status in {"ok", "dry_run"},
        "status": final_status,
        "config": str(source_config),
        "ignored_file": str(ignored_path),
        "discovered": sort_names(discovered),
        "iterations": iterations,
        "started_at_unix": int(time.time()),
    }
    if report_path:
        write_json(report_path, final)
    return final
