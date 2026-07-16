from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .rom import inspect_rom
from .util import atomic_write_text, run_command, which


@dataclass
class SplatConfigReport:
    config: str
    rom: str
    basename: str
    code_start: str
    vram: str
    end: str
    paths: dict[str, str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SplatHints:
    file_splits: list[dict]
    rodata_pairings: list[dict]
    rodata_starts: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def find_splat(explicit: str | None = None) -> str | None:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        resolved = which(explicit)
        if resolved:
            return resolved
        return None
    found = which("splat")
    if found:
        return found
    executable_dir = Path(sys.executable).expanduser().absolute().parent
    for name in ("splat.exe", "splat"):
        candidate = executable_dir / name
        if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)):
            return str(candidate)
    return None


def splat_status(splat: str | None = None) -> dict:
    path = find_splat(splat)
    data = {"path": path, "available": path is not None}
    if path:
        result = run_command([path, "--help"], timeout=15)
        text = (result.stdout or result.stderr).splitlines()
        data.update(
            {
                "help_returncode": result.returncode,
                "help_first_line": text[0] if text else "",
            }
        )
    return data


def _yaml_quote(text: str) -> str:
    return json.dumps(text)


def _write_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def create_splat_config(
    config_path: str | Path,
    *,
    rom_path: str | Path,
    basename: str,
    compiler: str = "IDO",
    code_start: int = 0x1000,
    vram: int = 0x80000400,
    end: int | None = None,
    overwrite: bool = False,
) -> SplatConfigReport:
    cfg = Path(config_path)
    if cfg.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing config: {cfg}")
    rom = Path(rom_path)
    if not rom.is_file():
        raise FileNotFoundError(f"ROM file not found: {rom}")
    info = inspect_rom(rom)
    if info.byte_order != "z64-big-endian":
        raise ValueError(f"Splat expects a normalized big-endian .z64 ROM; got {info.byte_order}")

    rom_size = rom.stat().st_size
    if end is None:
        end = rom_size
    if code_start < 0x1000:
        raise ValueError("code_start must be at or after 0x1000 for a normal N64 cartridge boot segment")
    if end <= code_start:
        raise ValueError("end offset must be larger than code_start")
    if end > rom_size:
        raise ValueError(f"end offset {hex(end)} is past ROM size {hex(rom_size)}")
    if vram % 4 != 0:
        raise ValueError("vram must be 4-byte aligned")

    base = cfg.parent if cfg.parent != Path("") else Path(".")
    dirs = {
        "asm": base / "asm",
        "src": base / "src",
        "assets": base / "assets",
        "build": base / "build",
        "symbols": base / "symbols",
    }
    for path in dirs.values():
        _write_dir(path)
    cfg.parent.mkdir(parents=True, exist_ok=True)

    rom_rel = relative_rom(cfg, rom)
    used_splat = False
    splat_bin = find_splat()
    if splat_bin:
        try:
            import shutil as _shutil
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                rom_copy = td_path / "baserom.z64"
                _shutil.copy2(rom, rom_copy)
                result = run_command([splat_bin, "create_config", str(rom_copy)], cwd=td_path, timeout=30)
                generated = sorted(td_path.glob("*.yaml"))
                if result.returncode == 0 and generated:
                    raw = generated[0].read_text(encoding="utf-8")
                    raw = _postprocess_splat_output(raw, basename, rom_rel)
                    atomic_write_text(cfg, raw)
                    used_splat = True
                    for src in td_path.glob("*.txt"):
                        dest = base / "symbols" / src.name
                        if not dest.exists():
                            _shutil.copy2(src, dest)
        except Exception:
            pass
    if not used_splat:
        _write_fallback_config(cfg, rom, basename, compiler, code_start, vram, end)

    return SplatConfigReport(
        config=str(cfg),
        rom=str(rom),
        basename=basename,
        code_start=hex(code_start),
        vram=hex(vram),
        end=hex(end),
        paths={name: str(path) for name, path in dirs.items()},
    )


def relative_rom(cfg: Path, rom: Path) -> str:
    return Path(os.path.relpath(rom.resolve(), start=cfg.parent.resolve())).as_posix()


def _write_fallback_config(
    cfg: Path, rom: Path, basename: str, compiler: str, code_start: int, vram: int, end: int
) -> None:
    rom_rel = relative_rom(cfg, rom)
    symbol_file = f"symbols/{basename}.symbols.txt"
    content = f"""options:
  base_path: "."
  platform: n64
  compiler: {_yaml_quote(compiler)}
  basename: {_yaml_quote(basename)}
  target_path: {_yaml_quote(rom_rel)}
  elf_path: {_yaml_quote("build/" + basename + ".elf")}

  # Paths
  asm_path: "asm"
  src_path: "src"
  build_path: "build"
  ld_script_path: {_yaml_quote(basename + ".ld")}
  cache_path: ".splache"
  asset_path: "assets"

  # Symbols
  symbol_addrs_path:
    - {_yaml_quote(symbol_file)}
  reloc_addrs_path:
    - symbols/reloc_addrs.txt
  undefined_funcs_auto_path: "symbols/undefined_funcs_auto.txt"
  undefined_syms_auto_path: "symbols/undefined_syms_auto.txt"

  # Disassembly
  find_file_boundaries: True
  header_encoding: ASCII
  o_as_suffix: True
  ld_dependencies: True
  create_asm_dependencies: True
  disassemble_all: True
  make_full_disasm_for_code: True

  # Symbol analysis
  dump_symbols: True
  dump_symbols_references: True

  # String detection
  rodata_string_guesser_level: 2
  data_string_guesser_level: 2

  # Assembly style
  mips_abi_float_regs: o32
  asm_function_macro: glabel
  asm_jtbl_label_macro: jlabel
  asm_data_macro: dlabel

  # Linker (uncomment as sections are mapped)
  # section_order: [".text", ".data", ".rodata", ".bss"]
  # auto_link_sections: [".data", ".rodata", ".bss"]

  # Extensions (optional)
  # extensions_path: tools/splat_ext

segments:
  - name: header
    type: header
    start: 0x0

  - name: ipl3
    type: bin
    start: 0x40

  - name: main
    type: code
    start: {hex(code_start)}
    vram: {hex(vram)}
    subsegments:
      - [{hex(code_start)}, asm]
      - [{hex(end)}]
"""
    atomic_write_text(cfg, content)


def _postprocess_splat_output(raw: str, basename: str, rom_rel: str) -> str:
    lines = raw.splitlines()
    splat_opts: dict[str, str] = {}
    segments_start = 0
    in_options = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "options:":
            in_options = True
            continue
        if stripped == "segments:":
            segments_start = i
            break
        if in_options and stripped and not stripped.startswith("#"):
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val:
                    splat_opts[key] = val
                elif i + 1 < len(lines):
                    list_vals: list[str] = []
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith("- "):
                        list_vals.append(lines[j].strip()[2:])
                        j += 1
                    if list_vals:
                        splat_opts[key] = "__list__:" + "|".join(list_vals)
                    else:
                        splat_opts[key] = ""

    compiler = splat_opts.get("compiler", "IDO")
    out_lines = [
        "options:",
        f'  base_path: "."',
        f"  platform: n64",
        f"  compiler: {_yaml_quote(compiler)}",
        f"  basename: {_yaml_quote(basename)}",
        f"  target_path: {_yaml_quote(rom_rel)}",
        f'  elf_path: {_yaml_quote("build/" + basename + ".elf")}',
        "",
        "  # Paths",
        '  asm_path: "asm"',
        '  src_path: "src"',
        '  build_path: "build"',
        f'  ld_script_path: {_yaml_quote(basename + ".ld")}',
        '  cache_path: ".splache"',
        '  asset_path: "assets"',
        "",
        "  # Symbols",
        "  symbol_addrs_path:",
        f"    - {_yaml_quote('symbols/' + basename + '.symbols.txt')}",
        "  reloc_addrs_path:",
        "    - symbols/reloc_addrs.txt",
        '  undefined_funcs_auto_path: "symbols/undefined_funcs_auto.txt"',
        '  undefined_syms_auto_path: "symbols/undefined_syms_auto.txt"',
        "",
        "  # Disassembly",
        "  find_file_boundaries: True",
        "  header_encoding: ASCII",
        "  o_as_suffix: True",
        "  ld_dependencies: True",
        "  create_asm_dependencies: True",
        f"  disassemble_all: True",
        f"  make_full_disasm_for_code: True",
        "",
        "  # Symbol analysis",
        "  dump_symbols: True",
        "  dump_symbols_references: True",
        "",
        "  # String detection",
        "  rodata_string_guesser_level: 2",
        "  data_string_guesser_level: 2",
        "",
        "  # Assembly style",
        "  mips_abi_float_regs: o32",
        "  asm_function_macro: glabel",
        "  asm_jtbl_label_macro: jlabel",
        "  asm_data_macro: dlabel",
        "",
        "  # Linker (uncomment as sections are mapped)",
        '  # section_order: [".text", ".data", ".rodata", ".bss"]',
        '  # auto_link_sections: [".data", ".rodata", ".bss"]',
        "",
        "  # Extensions (optional)",
        "  # extensions_path: tools/splat_ext",
        "",
    ]

    for line in lines[segments_start:]:
        out_lines.append(line)

    result = "\n".join(out_lines)
    result = result.replace("segments:\n\n", "segments:\n")
    return result


def parse_splat_hints(output: str) -> SplatHints:
    file_splits: list[dict] = []
    rodata_pairings: list[dict] = []
    rodata_starts: list[dict] = []

    lines = output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"Rodata segment\s+'(\S+)'\s+may belong to the text segment\s+'(\S+)'", line)
        if m:
            rodata_name = m.group(1)
            text_name = m.group(2)
            reason = ""
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                reason += lines[j].strip() + " "
                j += 1
            rodata_pairings.append({"rodata": rodata_name, "text": text_name, "reason": reason.strip()})
            i = j
            continue
        m = re.match(r"Data segment\s+(\S+),\s*symbol at vram\s+(\S+)\s+is a jumptable", line)
        if m:
            rodata_starts.append({"data_segment": m.group(1), "vram": m.group(2), "raw": line.strip()})
            i += 1
            continue
        if "File split suggestions for this segment will follow in config yaml format:" in line:
            segment_splits: list[str] = []
            j = i + 1
            while j < len(lines) and re.match(r"\s*- \[", lines[j]):
                segment_splits.append(lines[j].strip())
                j += 1
            if segment_splits:
                file_splits.append({"segment": segment_splits[0], "splits": segment_splits})
            i = j
            continue
        i += 1

    return SplatHints(file_splits=file_splits, rodata_pairings=rodata_pairings, rodata_starts=rodata_starts)


def run_splat_config(
    config_path: str | Path,
    *,
    splat: str | None = None,
    cwd: str | Path | None = None,
    timeout: int | None = None,
) -> dict:
    binary = find_splat(splat)
    if not binary:
        raise FileNotFoundError("splat command not found; install with: python3 -m pip install 'splat64[mips]==0.41.0'")
    cfg = Path(config_path)
    if not cfg.is_file():
        raise FileNotFoundError(f"Splat config not found: {cfg}")
    cfg = cfg.resolve()
    result = run_command([binary, "split", str(cfg)], cwd=cwd, timeout=timeout)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    hints = parse_splat_hints(combined)
    return {
        "ok": result.returncode == 0,
        "command": result.command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "seconds": result.seconds,
        "config": str(cfg),
        "hints": hints.to_dict(),
    }


def dump_symbols_csv(config_path: str | Path, *, splat: str | None = None, cwd: str | Path | None = None, timeout: int | None = None) -> dict:
    cfg = Path(config_path)
    binary = find_splat(splat)
    if not binary:
        raise FileNotFoundError("splat command not found")
    result = run_command([binary, "split", str(cfg.resolve())], cwd=cwd, timeout=timeout)
    csv_path = Path(cwd or ".") / ".splat" / "splat_symbols.csv"
    cross_refs: dict[str, list[str]] = {}
    count_by_type: dict[str, int] = {}
    count_by_subsegment: dict[str, int] = {}
    total = 0
    if csv_path.is_file():
        import csv
        with csv_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                total += 1
                stype = row.get("type", "?")
                sseg = row.get("subsegment", "?")
                count_by_type[stype] = count_by_type.get(stype, 0) + 1
                count_by_subsegment[sseg] = count_by_subsegment.get(sseg, 0) + 1
                refs = row.get("referenced_by", "")
                if refs:
                    cross_refs[row.get("name", "?")] = refs.split("|")
    return {
        "ok": result.returncode == 0,
        "total_symbols": total,
        "by_type": count_by_type,
        "by_subsegment": count_by_subsegment,
        "cross_references": len(cross_refs),
        "config": str(cfg.resolve()),
    }
