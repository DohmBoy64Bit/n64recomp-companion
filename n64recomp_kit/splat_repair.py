from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable

from ruamel.yaml import YAML
from ruamel.yaml.scalarint import HexInt

from .audit import sort_names
from .elf_build import build_elf_from_splat, load_elf_build_paths
from .util import atomic_write_bytes, atomic_write_text, backup_file, write_json

WORD_FUNC_RE = re.compile(r"(\.word\s+)(func_[0-9A-Fa-f]{6,8})\b", re.IGNORECASE)


def _iter_asm_files(asm_dir: str | Path) -> list[Path]:
    root = Path(asm_dir)
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise FileNotFoundError(f"asm path not found: {root}")
    return sorted([*root.rglob("*.s"), *root.rglob("*.S")])


def patch_data_asm(*, asm_dir: str | Path, symbols: Iterable[str] = (), dry_run: bool = False, report: str | Path | None = None) -> dict:
    """Annotate selected .word func_* references for data-pointer review."""
    wanted = set(symbols)
    changed_files = []
    replacements = []
    backups = []
    for path in _iter_asm_files(asm_dir):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        output_lines = []
        changed = False
        for line_number, line in enumerate(lines, 1):
            match = WORD_FUNC_RE.search(line)
            if match and (not wanted or match.group(2) in wanted) and "n64recomp-kit:data-pointer" not in line:
                new_line = line + "  # n64recomp-kit:data-pointer-review"
                replacements.append(
                    {
                        "path": str(path),
                        "line": line_number,
                        "symbol": match.group(2),
                        "before": line,
                        "after": new_line,
                    }
                )
                output_lines.append(new_line)
                changed = True
            else:
                output_lines.append(line)
        if changed:
            changed_files.append(str(path))
            if not dry_run:
                backup = backup_file(path)
                if backup:
                    backups.append(str(backup))
                atomic_write_text(path, "\n".join(output_lines) + "\n")
    data = {
        "ok": True,
        "dry_run": dry_run,
        "changed_files": changed_files,
        "backups": backups,
        "replacement_count": len(replacements),
        "replacements": replacements,
    }
    if report:
        write_json(report, data)
    return data


def patch_tail_asm(*, asm_dir: str | Path, prefix: str = "tail_", dry_run: bool = False, report: str | Path | None = None) -> dict:
    """Rename duplicate local labels across asm files using file-scoped names."""
    files = _iter_asm_files(asm_dir)
    labels_by_file: dict[Path, set[str]] = {}
    global_counts: dict[str, int] = {}
    for path in files:
        labels: set[str] = set()
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"^\s*([A-Za-z_.$][\w.$]*):", raw)
            if not match:
                continue
            label = match.group(1)
            if label.startswith(("func_", "D_")):
                continue
            labels.add(label)
            global_counts[label] = global_counts.get(label, 0) + 1
        labels_by_file[path] = labels
    duplicates = {label for label, count in global_counts.items() if count > 1}
    changes = []
    backups = []
    for path in files:
        labels = labels_by_file.get(path, set()) & duplicates
        if not labels:
            continue
        stem = re.sub(r"\W+", "_", path.stem)
        mapping = {label: f"{prefix}{stem}_{label.lstrip('.')}" for label in labels}
        text = path.read_text(encoding="utf-8", errors="replace")
        updated = text
        for old, new_name in mapping.items():
            updated = re.sub(rf"(^\s*){re.escape(old)}:", rf"\1{new_name}:", updated, flags=re.MULTILINE)
            updated = re.sub(rf"(?<![\w.$]){re.escape(old)}(?![\w.$])", new_name, updated)
        if updated != text:
            changes.append({"path": str(path), "renamed": mapping})
            if not dry_run:
                backup = backup_file(path)
                if backup:
                    backups.append(str(backup))
                atomic_write_text(path, updated)
    data = {
        "ok": True,
        "dry_run": dry_run,
        "duplicate_labels": sort_names(duplicates),
        "changed_files": len(changes),
        "backups": backups,
        "changes": changes,
    }
    if report:
        write_json(report, data)
    return data


def load_tail_split_hints(path: str | Path) -> list[int]:
    hints_path = Path(path)
    hints: list[int] = []
    if not hints_path.is_file():
        return hints
    for line_number, raw in enumerate(hints_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            value = int(line, 0)
        except ValueError as exc:
            raise ValueError(f"invalid split hint on line {line_number}: {line!r}") from exc
        if value < 0:
            raise ValueError(f"split hint on line {line_number} must be non-negative")
        hints.append(value)
    return sorted(set(hints))


def suggest_tail_split_hints(*, asm_dir: str | Path, min_gap: int = 0x4000, output: str | Path | None = None) -> dict:
    if min_gap <= 0:
        raise ValueError("min_gap must be greater than zero")
    starts = []
    for path in _iter_asm_files(asm_dir):
        match = re.search(r"([0-9A-Fa-f]{5,8})", path.stem)
        if match:
            starts.append(int(match.group(1), 16))
    starts = sorted(set(starts))
    hints = []
    previous = None
    for start in starts:
        if previous is None or start - previous >= min_gap:
            hints.append(start)
        previous = start
    if output:
        atomic_write_text(output, "\n".join(f"0x{value:X}" for value in hints) + ("\n" if hints else ""))
    return {
        "ok": True,
        "asm_dir": str(asm_dir),
        "hint_count": len(hints),
        "hints": [f"0x{value:X}" for value in hints],
        "output": str(output) if output else None,
    }


def apply_tail_split_hints(*, yaml_path: str | Path, hints_file: str | Path, segment_name: str = "tail", dry_run: bool = False, report: str | Path | None = None) -> dict:
    target = Path(yaml_path).resolve()
    yaml = YAML()
    yaml.preserve_quotes = True
    with target.open("r", encoding="utf-8") as handle:
        document = yaml.load(handle)
    if not isinstance(document, dict) or not isinstance(document.get("segments"), list):
        raise ValueError("Splat YAML must contain a segments list")
    segment = next(
        (item for item in document["segments"] if isinstance(item, dict) and item.get("name") == segment_name),
        None,
    )
    if segment is None:
        raise ValueError(f"could not find segment {segment_name!r}")
    subsegments = segment.get("subsegments")
    if not isinstance(subsegments, list):
        raise ValueError(f"segment {segment_name!r} does not contain a subsegments list")
    existing_offsets = {
        int(item[0])
        for item in subsegments
        if isinstance(item, list) and item and isinstance(item[0], int)
    }
    hints = load_tail_split_hints(hints_file)
    added = []
    for hint in hints:
        if hint in existing_offsets:
            continue
        subsegments.append([HexInt(hint), "asm", f"{segment_name}_{hint:X}"])
        existing_offsets.add(hint)
        added.append(f"0x{hint:X}")
    backup = None
    if added and not dry_run:
        backup_path = backup_file(target)
        backup = str(backup_path) if backup_path else None
        rendered = io.StringIO()
        yaml.dump(document, rendered)
        atomic_write_text(target, rendered.getvalue())
    data = {
        "ok": True,
        "dry_run": dry_run,
        "yaml": str(target),
        "hints_file": str(hints_file),
        "segment": segment_name,
        "backup": backup,
        "added": added,
    }
    if report:
        write_json(report, data)
    return data


def mips_link_preflight(*, config: str | Path, root: str | Path = ".", prefix: str | None = None, profile: str = "asm-only", timeout: int | None = None, dry_run: bool = True, report: str | Path | None = None) -> dict:
    paths = load_elf_build_paths(config, root_path=root)
    build = build_elf_from_splat(
        config,
        root_path=root,
        prefix=prefix,
        profile=profile,
        dry_run=dry_run,
        timeout=timeout,
    )
    data = {"ok": build.ok, "dry_run": dry_run, "paths": paths.to_dict(), "build": build.to_dict()}
    if report:
        write_json(report, data)
    return data


def recompiled_c_sanitize(*, path: str | Path, dry_run: bool = False, report: str | Path | None = None) -> dict:
    """Normalize CRLF to LF and remove NUL bytes from generated C/C++ text files."""
    root = Path(path)
    files = (
        [root]
        if root.is_file()
        else [item for item in root.rglob("*") if item.suffix.lower() in {".c", ".cc", ".cpp", ".h", ".hpp"}]
    )
    changed = []
    backups = []
    transformations = {"nul_bytes_removed": 0, "crlf_sequences_normalized": 0}
    for file_path in files:
        raw = file_path.read_bytes()
        nul_count = raw.count(b"\x00")
        crlf_count = raw.count(b"\r\n")
        updated = raw.replace(b"\x00", b"").replace(b"\r\n", b"\n")
        if updated != raw:
            changed.append(str(file_path))
            transformations["nul_bytes_removed"] += nul_count
            transformations["crlf_sequences_normalized"] += crlf_count
            if not dry_run:
                backup = backup_file(file_path)
                if backup:
                    backups.append(str(backup))
                atomic_write_bytes(file_path, updated)
    data = {
        "ok": True,
        "dry_run": dry_run,
        "files_scanned": len(files),
        "changed_files": changed,
        "backups": backups,
        "transformations": transformations,
    }
    if report:
        write_json(report, data)
    return data
