from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .util import atomic_write_text, backup_file, run_command, write_json

FUNC_NAME_RE = re.compile(r"^(?:func|ovl|Actor|En|Bg)_[0-9A-Fa-f_].*|^func_[0-9A-Fa-f]{8}$")
READ_ELF_LINE_RE = re.compile(
    r"^\s*\d+:\s+([0-9A-Fa-f]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+?)\s*$"
)


@dataclass(frozen=True)
class SymbolRow:
    value: int
    size: int
    type: str
    bind: str
    vis: str
    ndx: str
    name: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["value_hex"] = f"0x{self.value:08X}"
        return data


def parse_readelf_symbols_text(text: str) -> list[SymbolRow]:
    rows: list[SymbolRow] = []
    for line in text.splitlines():
        m = READ_ELF_LINE_RE.match(line)
        if not m:
            continue
        try:
            value = int(m.group(1), 16)
            size = int(m.group(2), 10)
        except ValueError:
            continue
        rows.append(SymbolRow(value, size, m.group(3), m.group(4), m.group(5), m.group(6), m.group(7).strip()))
    return rows


def load_symbol_rows(*, elf: str | Path | None = None, symbols_file: str | Path | None = None, readelf: str | None = None, prefix: str | None = None) -> tuple[list[SymbolRow], dict]:
    if symbols_file:
        p = Path(symbols_file)
        text = p.read_text(encoding="utf-8", errors="replace")
        return parse_readelf_symbols_text(text), {"source": "symbols_file", "path": str(p)}
    if not elf:
        raise ValueError("provide --elf or --symbols-file")
    elf_p = Path(elf)
    tool = readelf or ((prefix or "mips-linux-gnu-") + "readelf")
    result = run_command([tool, "-sW", str(elf_p)])
    if result.returncode != 0:
        raise RuntimeError(f"readelf failed: {result.stderr.strip() or result.stdout.strip()}")
    return parse_readelf_symbols_text(result.stdout), {"source": "readelf", "elf": str(elf_p), "command": result.to_dict()}


def is_real_function_symbol(row: SymbolRow) -> bool:
    if row.type != "FUNC" or row.size <= 0 or row.ndx == "UND":
        return False
    if row.name.startswith(("D_", ".L", "jtbl_")):
        return False
    return True


def sort_names(names: Iterable[str]) -> list[str]:
    def key(name: str):
        m = re.search(r"_([0-9A-Fa-f]{6,8})\b", name)
        return (0, int(m.group(1), 16)) if m else (1, name.lower())
    return sorted(set(n for n in names if n), key=key)


def parse_ranges(range_texts: Iterable[str]) -> list[tuple[str, int, int]]:
    ranges: list[tuple[str, int, int]] = []
    for raw in range_texts:
        parts = raw.split(":")
        if len(parts) != 3:
            raise ValueError("ranges must use name:start:end, for example main:0x80100000:0x80200000")
        name, lo, hi = parts
        ranges.append((name, int(lo, 0), int(hi, 0)))
    return ranges


def region_for(value: int, ranges: list[tuple[str, int, int]]) -> str:
    for name, lo, hi in ranges:
        if lo <= value < hi:
            return name
    return "other"


def export_functions(*, elf: str | Path | None = None, symbols_file: str | Path | None = None, out_dir: str | Path = "symbols/recomp", readelf: str | None = None, prefix: str | None = None, ranges: Iterable[str] = ()) -> dict:
    rows, meta = load_symbol_rows(elf=elf, symbols_file=symbols_file, readelf=readelf, prefix=prefix)
    real = [r for r in rows if is_real_function_symbol(r)]
    parsed_ranges = parse_ranges(ranges)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    all_path = out / "sized-funcs.tsv"
    all_lines = ["# vram_hex\tsize\tname\tsection_ndx\tregion"]
    all_lines.extend(
        f"0x{row.value:08X}\t{row.size}\t{row.name}\t{row.ndx}\t{region_for(row.value, parsed_ranges)}"
        for row in sorted(real, key=lambda r: (r.value, r.name))
    )
    atomic_write_text(all_path, "\n".join(all_lines) + "\n")
    region_counts: dict[str, int] = {}
    if parsed_ranges:
        by_region: dict[str, list[SymbolRow]] = {}
        for row in real:
            reg = region_for(row.value, parsed_ranges)
            by_region.setdefault(reg, []).append(row)
        for reg, reg_rows in by_region.items():
            region_counts[reg] = len(reg_rows)
            path = out / f"sized-funcs-{reg}.tsv"
            region_lines = ["# vram_hex\tsize\tname\tsection_ndx"]
            region_lines.extend(
                f"0x{row.value:08X}\t{row.size}\t{row.name}\t{row.ndx}"
                for row in sorted(reg_rows, key=lambda r: (r.value, r.name))
            )
            atomic_write_text(path, "\n".join(region_lines) + "\n")
    report = {
        "ok": True,
        "meta": meta,
        "total_symbols": len(rows),
        "exported_functions": len(real),
        "out_dir": str(out),
        "files": [str(all_path)],
        "region_counts": region_counts,
    }
    write_json(out / "export-functions-report.json", report)
    return report


def read_names_file(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.is_file():
        return []
    names: list[str] = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip().strip('"').rstrip(",")
        if line:
            names.append(line)
    return names


def read_sized_tsv_names(path: str | Path) -> set[str]:
    p = Path(path)
    names: set[str] = set()
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) >= 4:
            try:
                if int(parts[1], 10) <= 0:
                    continue
            except ValueError:
                continue
            if parts[3] in {"UND", "ABS"} or parts[3].startswith("-"):
                continue
            names.add(parts[2])
    return names


def filter_ignored_by_export(*, sized_tsv: str | Path, ignored_files: Iterable[str | Path], dry_run: bool = False) -> dict:
    valid = read_sized_tsv_names(sized_tsv)
    files_report = []
    total_dropped = 0
    for file in ignored_files:
        p = Path(file)
        original_lines = p.read_text(encoding="utf-8", errors="replace").splitlines() if p.is_file() else []
        kept_lines: list[str] = []
        dropped: list[str] = []
        for raw in original_lines:
            name = raw.split("#", 1)[0].strip().strip('"').rstrip(",")
            if not name or raw.lstrip().startswith("#"):
                kept_lines.append(raw)
            elif name in valid:
                kept_lines.append(name)
            else:
                dropped.append(name)
        total_dropped += len(dropped)
        if not dry_run and p.is_file():
            names = [ln for ln in kept_lines if ln and not ln.lstrip().startswith("#")]
            comments = [ln for ln in kept_lines if ln.lstrip().startswith("#")]
            backup_file(p)
            atomic_write_text(p, "\n".join(comments + sort_names(names)) + ("\n" if kept_lines else ""))
        files_report.append({"path": str(p), "kept": len(kept_lines) - len([ln for ln in kept_lines if ln.lstrip().startswith('#')]), "dropped": dropped})
    return {"ok": True, "dry_run": dry_run, "sized_tsv": str(sized_tsv), "valid_function_count": len(valid), "total_dropped": total_dropped, "files": files_report}


def elf_symbol_audit(*, elf: str | Path | None = None, symbols_file: str | Path | None = None, readelf: str | None = None, prefix: str | None = None, alias_policy: str = "allow") -> dict:
    if alias_policy not in {"allow", "warn", "error"}:
        raise ValueError("alias_policy must be allow, warn, or error")
    rows, meta = load_symbol_rows(elf=elf, symbols_file=symbols_file, readelf=readelf, prefix=prefix)
    funcs = [r for r in rows if r.type == "FUNC"]
    sized = [r for r in funcs if r.size > 0 and r.ndx != "UND"]
    zero = [r for r in funcs if r.size <= 0 and r.ndx != "UND"]
    undefined = [r for r in funcs if r.ndx == "UND"]
    by_addr: dict[int, list[SymbolRow]] = {}
    for row in sized:
        by_addr.setdefault(row.value, []).append(row)
    aliases = [
        {
            "value_hex": f"0x{addr:08X}",
            "names": [r.name for r in rs],
            "sizes": sorted({r.size for r in rs}),
        }
        for addr, rs in sorted(by_addr.items()) if len(rs) > 1
    ]
    overlaps = []
    last: SymbolRow | None = None
    for row in sorted(sized, key=lambda r: (r.value, r.size, r.name)):
        same_start_alias = bool(last and row.value == last.value)
        if last and not same_start_alias and row.value < last.value + last.size:
            overlaps.append({
                "previous": last.to_dict(),
                "current": row.to_dict(),
                "overlap_bytes": last.value + last.size - row.value,
            })
        if last is None or row.value + row.size > last.value + last.size:
            last = row
    alias_errors = len(aliases) if alias_policy == "error" else 0
    issues = len(zero) + len(undefined) + alias_errors + len(overlaps)
    return {
        "ok": issues == 0,
        "meta": meta,
        "function_count": len(funcs),
        "sized_function_count": len(sized),
        "issues": {
            "zero_size_functions": [r.to_dict() for r in zero],
            "undefined_functions": [r.to_dict() for r in undefined],
            "aliases": aliases,
            "alias_policy": alias_policy,
            "overlaps": overlaps,
        },
        "alias_count": len(aliases),
        "issue_count": issues,
    }
