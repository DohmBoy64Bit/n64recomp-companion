from __future__ import annotations

import json
import re
from pathlib import Path

from .util import atomic_write_bytes, read_bytes, write_json

MAP_LINE_RE = re.compile(r"^\s*(?:0x)?([0-9A-Fa-f]{1,16})\s+(?:0x)?([0-9A-Fa-f]{1,16})\s+(.+?)\s*$")


def first_mismatch(a: bytes, b: bytes, limit: int | None = None) -> int | None:
    n = min(len(a), len(b), limit if limit is not None else max(len(a), len(b)))
    for i in range(n):
        if a[i] != b[i]:
            return i
    if limit is None and len(a) != len(b):
        return n
    return None


def _byte_at(data: bytes, offset: int) -> int | None:
    return data[offset] if 0 <= offset < len(data) else None


def rom_match_check(*, expected: str | Path, actual: str | Path, start: int = 0, size: int | None = None, report: str | Path | None = None) -> dict:
    if start < 0:
        raise ValueError("start must be non-negative")
    if size is not None and size < 0:
        raise ValueError("size must be non-negative")
    exp = read_bytes(expected)
    act = read_bytes(actual)
    exp_slice = exp[start : start + size if size is not None else None]
    act_slice = act[start : start + size if size is not None else None]
    mismatch = first_mismatch(exp_slice, act_slice)
    ok = mismatch is None and len(exp_slice) == len(act_slice)
    data = {
        "ok": ok,
        "expected": str(expected),
        "actual": str(actual),
        "start": start,
        "size": size if size is not None else len(exp_slice),
        "expected_size": len(exp_slice),
        "actual_size": len(act_slice),
        "first_mismatch": None
        if mismatch is None
        else {
            "relative": mismatch,
            "absolute": start + mismatch,
            "expected_byte": _byte_at(exp_slice, mismatch),
            "actual_byte": _byte_at(act_slice, mismatch),
        },
    }
    if report:
        write_json(report, data)
    return data


def _load_manifest(path: str | Path) -> tuple[Path, list[dict]]:
    p = Path(path).resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("sections", [])
    if not isinstance(data, list):
        raise ValueError("section manifest must be a JSON list or an object with a sections list")
    if not data:
        raise ValueError("section manifest contains no sections")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError("every section manifest entry must be an object")
    return p, data


def _resolve_manifest_path(manifest_path: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"section field {field!r} must be a non-empty path string")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (manifest_path.parent / path).resolve()


def _parse_non_negative_int(value: object, field: str) -> int:
    try:
        parsed = int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"section field {field!r} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"section field {field!r} must be non-negative")
    return parsed


def rom_match_sections(*, manifest: str | Path, report: str | Path | None = None) -> dict:
    manifest_path, sections = _load_manifest(manifest)
    results = []
    ok = True
    for index, sec in enumerate(sections):
        name = sec.get("name") or f"section_{index}"
        expected = _resolve_manifest_path(manifest_path, sec.get("expected"), "expected")
        actual = _resolve_manifest_path(manifest_path, sec.get("actual"), "actual")
        exp_off = _parse_non_negative_int(sec.get("expected_offset", sec.get("offset", 0)), "expected_offset")
        act_off = _parse_non_negative_int(sec.get("actual_offset", sec.get("offset", 0)), "actual_offset")
        size = _parse_non_negative_int(sec.get("size"), "size")
        if size == 0:
            raise ValueError(f"section {name!r} has a zero size")
        exp = read_bytes(expected)[exp_off : exp_off + size]
        act = read_bytes(actual)[act_off : act_off + size]
        mismatch = first_mismatch(exp, act)
        sec_ok = mismatch is None and len(exp) == len(act) == size
        ok = ok and sec_ok
        results.append(
            {
                "name": name,
                "ok": sec_ok,
                "expected": str(expected),
                "actual": str(actual),
                "expected_offset": exp_off,
                "actual_offset": act_off,
                "size": size,
                "first_mismatch": None
                if mismatch is None
                else {
                    "relative": mismatch,
                    "expected_byte": _byte_at(exp, mismatch),
                    "actual_byte": _byte_at(act, mismatch),
                },
            }
        )
    data = {"ok": ok, "manifest": str(manifest_path), "section_count": len(results), "sections": results}
    if report:
        write_json(report, data)
    return data


def parse_simple_map(path: str | Path) -> list[dict]:
    map_path = Path(path)
    rows: list[dict] = []
    errors: list[str] = []
    for line_number, raw in enumerate(map_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = MAP_LINE_RE.match(line)
        if not match:
            errors.append(f"line {line_number}: expected OFFSET SIZE SOURCE")
            continue
        offset = int(match.group(1), 16)
        size = int(match.group(2), 16)
        source = match.group(3).strip()
        if size <= 0:
            errors.append(f"line {line_number}: size must be greater than zero")
            continue
        rows.append({"offset": offset, "size": size, "source": source, "line": line_number})
    if errors:
        raise ValueError("malformed ROM map:\n" + "\n".join(errors))
    if not rows:
        raise ValueError("ROM map contains no usable entries")
    return rows


def rom_build_from_map(*, map_file: str | Path, output: str | Path, fill: int = 0, root: str | Path | None = None, size: int | None = None, dry_run: bool = False, report: str | Path | None = None) -> dict:
    if not 0 <= fill <= 0xFF:
        raise ValueError("fill must be between 0 and 255")
    if size is not None and size <= 0:
        raise ValueError("size must be greater than zero")
    map_path = Path(map_file).resolve()
    root_p = Path(root).resolve() if root is not None else map_path.parent
    rows = parse_simple_map(map_path)
    total = size if size is not None else max(r["offset"] + r["size"] for r in rows)
    if any(r["offset"] + r["size"] > total for r in rows):
        raise ValueError("one or more map entries extend past the requested output size")
    ordered = sorted(rows, key=lambda row: (row["offset"], row["line"]))
    for previous, current in zip(ordered, ordered[1:]):
        previous_end = previous["offset"] + previous["size"]
        if current["offset"] < previous_end:
            raise ValueError(
                f"ROM map entries overlap: lines {previous['line']} and {current['line']}"
            )
    image = bytearray([fill]) * total
    copied = []
    for row in rows:
        src = Path(row["source"])
        if not src.is_absolute():
            src = root_p / src
        src = src.resolve()
        if not src.is_file():
            copied.append({**row, "source": str(src), "ok": False, "error": f"missing source: {src}"})
            continue
        source_data = src.read_bytes()
        if len(source_data) < row["size"]:
            copied.append(
                {
                    **row,
                    "source": str(src),
                    "ok": False,
                    "error": f"source is {len(source_data)} bytes; map requests {row['size']} bytes",
                }
            )
            continue
        image[row["offset"] : row["offset"] + row["size"]] = source_data[: row["size"]]
        copied.append({**row, "source": str(src), "ok": True})
    ok = bool(copied) and all(row.get("ok") for row in copied)
    if not dry_run and ok:
        atomic_write_bytes(output, bytes(image))
    data = {
        "ok": ok,
        "dry_run": dry_run,
        "map_file": str(map_path),
        "root": str(root_p),
        "output": str(output),
        "size": len(image),
        "copied": copied,
    }
    if report:
        write_json(report, data)
    return data
