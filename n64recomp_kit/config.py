from __future__ import annotations

import json
import shutil
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .util import atomic_write_text


@dataclass
class Diagnostic:
    severity: str
    message: str
    key: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfigValidation:
    path: str
    ok: bool
    diagnostics: list[Diagnostic]
    resolved_paths: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "ok": self.ok,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "resolved_paths": self.resolved_paths,
        }


PATH_FIELDS = {
    "elf_path",
    "symbols_file_path",
    "rom_file_path",
    "output_func_path",
    "relocatable_sections_path",
    "output_binary_path",
    "func_reference_syms_file",
}
ARRAY_PATH_FIELDS = {"data_reference_syms_files"}
BOOL_FIELDS = {
    "uses_mips3_float_mode",
    "single_file_output",
    "use_absolute_symbols",
    "unpaired_lo16_warnings",
    "use_mdebug",
    "trace_mode",
    "allow_exports",
    "strict_patch_mode",
}
INT_FIELDS = {"entrypoint", "functions_per_output_file"}
STRING_FIELDS = {"bss_section_suffix", "recomp_include"}

KNOWN_INPUT_FIELDS = (
    PATH_FIELDS
    | ARRAY_PATH_FIELDS
    | BOOL_FIELDS
    | INT_FIELDS
    | STRING_FIELDS
    | {"manual_funcs", "function_sizes", "mdebug_file_mappings"}
)
KNOWN_PATCH_FIELDS = {"stubs", "ignored", "renamed", "instruction", "hook"}
KNOWN_TOP_LEVEL_FIELDS = {"input", "patches"}
MDEBUG_INPUT_SECTIONS = {".text", ".data", ".rodata", ".bss"}


def _diag(diags: list[Diagnostic], severity: str, message: str, key: str | None = None) -> None:
    diags.append(Diagnostic(severity, message, key))


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _resolve(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_word_aligned(value: int) -> bool:
    return (value & 0b11) == 0


def validate_config(path: str | Path, *, allow_missing_paths: bool = False) -> ConfigValidation:
    p = Path(path)
    diagnostics: list[Diagnostic] = []
    resolved: dict[str, str] = {}
    if not p.exists():
        return ConfigValidation(str(p), False, [Diagnostic("error", "config file does not exist", None)], {})
    try:
        data = _load(p)
    except tomllib.TOMLDecodeError as exc:
        return ConfigValidation(str(p), False, [Diagnostic("error", f"TOML parse error: {exc}", None)], {})
    base = p.parent
    for key in sorted(set(data) - KNOWN_TOP_LEVEL_FIELDS):
        _diag(diagnostics, "warning", "unknown top-level key; verify spelling and upstream compatibility", key)
    input_data = data.get("input")
    if not isinstance(input_data, dict):
        _diag(diagnostics, "error", "missing required [input] table", "input")
        return ConfigValidation(str(p), False, diagnostics, resolved)

    output_func_path = input_data.get("output_func_path")
    if not isinstance(output_func_path, str) or not output_func_path:
        _diag(diagnostics, "error", "[input].output_func_path is required and must be a non-empty string", "input.output_func_path")

    has_elf = isinstance(input_data.get("elf_path"), str) and bool(input_data.get("elf_path"))
    has_symbols = isinstance(input_data.get("symbols_file_path"), str) and bool(input_data.get("symbols_file_path"))
    has_rom = isinstance(input_data.get("rom_file_path"), str) and bool(input_data.get("rom_file_path"))
    if not has_elf and not (has_symbols and has_rom):
        _diag(
            diagnostics,
            "error",
            "provide either [input].elf_path or both [input].symbols_file_path and [input].rom_file_path",
            "input",
        )
    if has_elf and (has_symbols or has_rom):
        _diag(
            diagnostics,
            "warning",
            "both ELF input and symbol/ROM input are present; verify this matches the intended N64Recomp mode",
            "input",
        )

    for key, value in input_data.items():
        full_key = f"input.{key}"
        if key in PATH_FIELDS:
            if isinstance(value, str) and value:
                rp = _resolve(base, value)
                resolved[full_key] = str(rp)
                if key != "output_func_path" and not allow_missing_paths and not rp.exists():
                    _diag(diagnostics, "error", f"path does not exist: {rp}", full_key)
            elif value not in (None, ""):
                _diag(diagnostics, "error", "path value must be a string", full_key)
        elif key in ARRAY_PATH_FIELDS:
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                _diag(diagnostics, "error", "must be an array of non-empty strings", full_key)
            else:
                for idx, item in enumerate(value):
                    rp = _resolve(base, item)
                    resolved[f"{full_key}[{idx}]"] = str(rp)
                    if not allow_missing_paths and not rp.exists():
                        _diag(diagnostics, "error", f"path does not exist: {rp}", f"{full_key}[{idx}]")
        elif key in BOOL_FIELDS:
            if not isinstance(value, bool):
                _diag(diagnostics, "error", "must be a boolean", full_key)
        elif key in INT_FIELDS:
            if not _is_int(value):
                _diag(diagnostics, "error", "must be an integer", full_key)
            elif key == "entrypoint" and not _is_word_aligned(value):
                _diag(diagnostics, "error", "entrypoint must be word-aligned", full_key)
            elif key == "functions_per_output_file" and value <= 0:
                _diag(diagnostics, "error", "functions_per_output_file must be greater than zero", full_key)
        elif key in STRING_FIELDS:
            if not isinstance(value, str):
                _diag(diagnostics, "error", "must be a string", full_key)
        elif key == "manual_funcs":
            _validate_manual_funcs(value, diagnostics, full_key)
        elif key == "function_sizes":
            _validate_function_sizes(value, diagnostics, full_key)
        elif key == "mdebug_file_mappings":
            _validate_mdebug_file_mappings(value, diagnostics, full_key)
        elif key not in KNOWN_INPUT_FIELDS:
            _diag(diagnostics, "warning", "unknown [input] key; verify spelling and upstream compatibility", full_key)

    if has_symbols and input_data.get("func_reference_syms_file"):
        _diag(
            diagnostics,
            "error",
            "func_reference_syms_file is only valid in ELF input mode according to upstream config parser behavior",
            "input.func_reference_syms_file",
        )
    if input_data.get("data_reference_syms_files") and not input_data.get("func_reference_syms_file"):
        _diag(
            diagnostics,
            "error",
            "data_reference_syms_files requires func_reference_syms_file",
            "input.data_reference_syms_files",
        )

    patches = data.get("patches")
    if patches is not None:
        if not isinstance(patches, dict):
            _diag(diagnostics, "error", "[patches] must be a table", "patches")
        else:
            _validate_patches(patches, diagnostics)

    ok = not any(d.severity == "error" for d in diagnostics)
    return ConfigValidation(str(p), ok, diagnostics, resolved)


def _validate_manual_funcs(value: Any, diagnostics: list[Diagnostic], key: str) -> None:
    if not isinstance(value, list):
        _diag(diagnostics, "error", "manual_funcs must be an array of tables", key)
        return
    for idx, item in enumerate(value):
        item_key = f"{key}[{idx}]"
        if not isinstance(item, dict):
            _diag(diagnostics, "error", "manual function entry must be a table", item_key)
            continue
        for required in ("name", "section", "vram", "size"):
            if required not in item:
                _diag(diagnostics, "error", f"missing required field {required!r}", item_key)
        if "name" in item and not isinstance(item["name"], str):
            _diag(diagnostics, "error", "name must be a string", f"{item_key}.name")
        if "section" in item and not isinstance(item["section"], str):
            _diag(diagnostics, "error", "section must be a string", f"{item_key}.section")
        if "vram" in item and (not _is_int(item["vram"]) or not _is_word_aligned(item["vram"])):
            _diag(diagnostics, "error", "vram must be a word-aligned integer", f"{item_key}.vram")
        if "size" in item and (not _is_int(item["size"]) or item["size"] <= 0 or item["size"] % 4 != 0):
            _diag(diagnostics, "error", "size must be a positive multiple of 4", f"{item_key}.size")


def _validate_mdebug_file_mappings(value: Any, diagnostics: list[Diagnostic], key: str) -> None:
    if not isinstance(value, list):
        _diag(diagnostics, "error", "mdebug_file_mappings must be an array of tables", key)
        return
    for idx, item in enumerate(value):
        item_key = f"{key}[{idx}]"
        if not isinstance(item, dict):
            _diag(diagnostics, "error", "mdebug file mapping entry must be a table", item_key)
            continue
        for required in ("filename", "input_section", "output_section"):
            if required not in item:
                _diag(diagnostics, "error", f"missing required field {required!r}", item_key)
            elif not isinstance(item[required], str) or not item[required]:
                _diag(diagnostics, "error", f"{required} must be a non-empty string", f"{item_key}.{required}")
        input_section = item.get("input_section")
        if isinstance(input_section, str) and input_section not in MDEBUG_INPUT_SECTIONS:
            _diag(
                diagnostics,
                "error",
                f"input_section must be one of {sorted(MDEBUG_INPUT_SECTIONS)}",
                f"{item_key}.input_section",
            )
        for extra in sorted(set(item) - {"filename", "input_section", "output_section"}):
            _diag(diagnostics, "warning", "unknown mdebug mapping key", f"{item_key}.{extra}")


def _validate_function_sizes(value: Any, diagnostics: list[Diagnostic], key: str) -> None:
    if not isinstance(value, list):
        _diag(diagnostics, "error", "function_sizes must be an array of tables", key)
        return
    for idx, item in enumerate(value):
        item_key = f"{key}[{idx}]"
        if not isinstance(item, dict):
            _diag(diagnostics, "error", "function size entry must be a table", item_key)
            continue
        name = item.get("name")
        size = item.get("size")
        if not isinstance(name, str) or not name:
            _diag(diagnostics, "error", "name must be a non-empty string", f"{item_key}.name")
        if not _is_int(size) or size <= 0 or size % 4 != 0:
            _diag(diagnostics, "error", "size must be a positive multiple of 4", f"{item_key}.size")


def _validate_patches(patches: dict[str, Any], diagnostics: list[Diagnostic]) -> None:
    for key in sorted(set(patches) - KNOWN_PATCH_FIELDS):
        _diag(diagnostics, "warning", "unknown [patches] key; verify spelling and upstream compatibility", f"patches.{key}")
    for array_name in ("stubs", "ignored", "renamed"):
        value = patches.get(array_name)
        if value is not None and (not isinstance(value, list) or not all(isinstance(v, str) and v for v in value)):
            _diag(diagnostics, "error", f"patches.{array_name} must be an array of non-empty strings", f"patches.{array_name}")
    instruction = patches.get("instruction")
    if instruction is not None:
        if not isinstance(instruction, list):
            _diag(diagnostics, "error", "patches.instruction must be an array of tables", "patches.instruction")
        else:
            for idx, item in enumerate(instruction):
                item_key = f"patches.instruction[{idx}]"
                if not isinstance(item, dict):
                    _diag(diagnostics, "error", "instruction patch entry must be a table", item_key)
                    continue
                for req in ("func", "vram", "value"):
                    if req not in item:
                        _diag(diagnostics, "error", f"missing required field {req!r}", item_key)
                if "func" in item and not isinstance(item["func"], str):
                    _diag(diagnostics, "error", "func must be a string", f"{item_key}.func")
                if "vram" in item and (not _is_int(item["vram"]) or not _is_word_aligned(item["vram"])):
                    _diag(diagnostics, "error", "vram must be a word-aligned integer", f"{item_key}.vram")
                if "value" in item and not _is_int(item["value"]):
                    _diag(diagnostics, "error", "value must be an integer", f"{item_key}.value")
    hooks = patches.get("hook")
    if hooks is not None:
        if not isinstance(hooks, list):
            _diag(diagnostics, "error", "patches.hook must be an array of tables", "patches.hook")
        else:
            for idx, item in enumerate(hooks):
                item_key = f"patches.hook[{idx}]"
                if not isinstance(item, dict):
                    _diag(diagnostics, "error", "hook entry must be a table", item_key)
                    continue
                if not isinstance(item.get("func"), str) or not item.get("func"):
                    _diag(diagnostics, "error", "func must be a non-empty string", f"{item_key}.func")
                if not isinstance(item.get("text"), str):
                    _diag(diagnostics, "error", "text must be a string", f"{item_key}.text")
                if "before_vram" in item and (not _is_int(item["before_vram"]) or not _is_word_aligned(item["before_vram"])):
                    _diag(diagnostics, "error", "before_vram must be a word-aligned integer", f"{item_key}.before_vram")


def format_validation(result: ConfigValidation) -> str:
    lines = [f"Config: {result.path}", f"Status: {'OK' if result.ok else 'FAILED'}"]
    if result.resolved_paths:
        lines.append("Resolved paths:")
        for key, value in sorted(result.resolved_paths.items()):
            lines.append(f"  {key}: {value}")
    if result.diagnostics:
        lines.append("Diagnostics:")
        for diag in result.diagnostics:
            loc = f" [{diag.key}]" if diag.key else ""
            lines.append(f"  {diag.severity.upper()}{loc}: {diag.message}")
    return "\n".join(lines)


def create_config(
    output: str | Path,
    *,
    entrypoint: int | None,
    elf_path: str | None,
    rom_path: str | None,
    symbols_file_path: str | None,
    output_func_path: str,
    relocatable_sections_path: str | None = None,
    single_file_output: bool = False,
    functions_per_output_file: int = 50,
    recomp_include: str = '#include "recomp.h"',
    overwrite: bool = False,
) -> Path:
    out = Path(output)
    if out.exists() and not overwrite:
        raise FileExistsError(f"config already exists: {out}")
    if not elf_path and not (rom_path and symbols_file_path):
        raise ValueError("provide either elf_path or both rom_path and symbols_file_path")
    if functions_per_output_file <= 0:
        raise ValueError("functions_per_output_file must be greater than zero")
    lines = ["[input]"]
    if entrypoint is not None:
        lines.append(f"entrypoint = 0x{entrypoint:X}")
    if elf_path:
        lines.append(f"elf_path = {json.dumps(elf_path)}")
    if symbols_file_path:
        lines.append(f"symbols_file_path = {json.dumps(symbols_file_path)}")
    if rom_path:
        lines.append(f"rom_file_path = {json.dumps(rom_path)}")
    lines.append(f"output_func_path = {json.dumps(output_func_path)}")
    if relocatable_sections_path:
        lines.append(f"relocatable_sections_path = {json.dumps(relocatable_sections_path)}")
    lines.append(f"single_file_output = {'true' if single_file_output else 'false'}")
    lines.append(f"functions_per_output_file = {functions_per_output_file}")
    lines.append(f"recomp_include = {json.dumps(recomp_include)}")
    lines.append("")
    lines.append("[patches]")
    lines.append("stubs = []")
    lines.append("ignored = []")
    lines.append("renamed = []")
    atomic_write_text(out, "\n".join(lines) + "\n")
    return out
