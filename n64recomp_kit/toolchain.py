from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .elf import inspect_elf
from .util import atomic_write_text, run_command, which

PREFERRED_MIPS_PREFIXES = [
    "mips64-elf-",
    "mips64-ultra-elf-",
    "mips64-n64-elf-",
    "mips-linux-gnu-",
    "mips64-linux-gnuabi64-",
    "mipsel-linux-gnu-",
]

REQUIRED_BINUTILS = ["as", "ld", "objdump", "readelf", "nm", "objcopy"]
OPTIONAL_COMPILERS = ["gcc", "g++"]


@dataclass
class ToolProbe:
    name: str
    command: str
    path: str | None
    available: bool
    version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolchainProbe:
    prefix: str
    tools: list[ToolProbe]
    complete_binutils: bool
    has_c_compiler: bool

    @property
    def usable_for_elf_smoke(self) -> bool:
        names = {tool.name: tool.available for tool in self.tools}
        return bool(names.get("as") and names.get("ld") and names.get("readelf"))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["usable_for_elf_smoke"] = self.usable_for_elf_smoke
        return data


def _version_for(path: str) -> str:
    result = run_command([path, "--version"], timeout=10)
    text = (result.stdout or result.stderr).splitlines()
    return text[0] if text else ""


def _probe_tool(prefix: str, name: str) -> ToolProbe:
    command = f"{prefix}{name}"
    path = which(command)
    return ToolProbe(
        name=name,
        command=command,
        path=path,
        available=path is not None,
        version=_version_for(path) if path else "",
    )


def discover_mips_toolchains(prefixes: Iterable[str] | None = None) -> list[ToolchainProbe]:
    found: list[ToolchainProbe] = []
    for prefix in prefixes or PREFERRED_MIPS_PREFIXES:
        tools = [_probe_tool(prefix, name) for name in REQUIRED_BINUTILS + OPTIONAL_COMPILERS]
        if any(tool.available for tool in tools):
            available_required = {tool.name for tool in tools if tool.available and tool.name in REQUIRED_BINUTILS}
            found.append(
                ToolchainProbe(
                    prefix=prefix,
                    tools=tools,
                    complete_binutils=all(name in available_required for name in REQUIRED_BINUTILS),
                    has_c_compiler=any(tool.available and tool.name == "gcc" for tool in tools),
                )
            )
    return found


def choose_toolchain(prefix: str | None = None) -> ToolchainProbe | None:
    probes = discover_mips_toolchains([prefix] if prefix else None)
    if prefix:
        return probes[0] if probes else None
    for probe in probes:
        if probe.usable_for_elf_smoke:
            return probe
    return probes[0] if probes else None


def format_toolchains(probes: list[ToolchainProbe]) -> str:
    if not probes:
        return "No MIPS cross toolchains found on PATH."
    lines: list[str] = []
    for probe in probes:
        status = "usable" if probe.usable_for_elf_smoke else "partial"
        compiler = "gcc" if probe.has_c_compiler else "binutils only"
        lines.append(f"{probe.prefix} ({status}, {compiler})")
        for tool in probe.tools:
            marker = "yes" if tool.available else "no"
            line = f"  {tool.command:<30} {marker:<3} {tool.path or ''}"
            if tool.version:
                line += f"  {tool.version}"
            lines.append(line)
    return "\n".join(lines)


def smoke_test_mips_toolchain(
    *,
    output_dir: str | Path,
    prefix: str | None = None,
    vram: int = 0x80000400,
) -> dict:
    probe = choose_toolchain(prefix)
    if probe is None:
        raise RuntimeError("no MIPS toolchain prefix was found on PATH")
    if not probe.usable_for_elf_smoke:
        raise RuntimeError(f"toolchain prefix {probe.prefix!r} is missing as, ld, or readelf")

    tools = {tool.name: tool.path for tool in probe.tools}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    asm_path = out / "n64_smoke.s"
    obj_path = out / "n64_smoke.o"
    elf_path = out / "n64_smoke.elf"
    atomic_write_text(
        asm_path,
        ".set noreorder\n"
        ".set noat\n"
        ".section .text\n"
        ".globl _start\n"
        "_start:\n"
        "    jr $ra\n"
        "    nop\n",
    )

    as_cmd = [tools["as"], "-EB", "-mips3", "-o", str(obj_path), str(asm_path)]
    as_cmd = [part for part in as_cmd if part is not None]
    as_result = run_command(as_cmd, timeout=30)
    if as_result.returncode != 0:
        return {
            "ok": False,
            "prefix": probe.prefix,
            "stage": "assemble",
            "assembler": as_result.to_dict(),
            "paths": {"asm": str(asm_path), "object": str(obj_path), "elf": str(elf_path)},
        }

    ld_cmd = [tools["ld"], "-Ttext", hex(vram), "-e", "_start", "-o", str(elf_path), str(obj_path)]
    ld_cmd = [part for part in ld_cmd if part is not None]
    ld_result = run_command(ld_cmd, timeout=30)
    if ld_result.returncode != 0:
        return {
            "ok": False,
            "prefix": probe.prefix,
            "stage": "link",
            "assembler": as_result.to_dict(),
            "linker": ld_result.to_dict(),
            "paths": {"asm": str(asm_path), "object": str(obj_path), "elf": str(elf_path)},
        }

    readelf_result = run_command([tools["readelf"], "-h", str(elf_path)], timeout=30)
    header = inspect_elf(elf_path).to_dict() if readelf_result.returncode == 0 else None
    readelf_text = readelf_result.stdout.lower()
    checks = {
        "elf32": bool(header and header.get("elf_class") == "ELF32" and "elf32" in readelf_text),
        "big_endian": bool(header and header.get("endian") == "big" and "big endian" in readelf_text),
        "mips_machine": bool(header and header.get("machine_id") == 8 and "mips" in readelf_text),
        "entrypoint": bool(header and int(header.get("entrypoint", "0"), 0) == vram),
        "mips3_flags": "mips3" in readelf_text,
    }
    ok = readelf_result.returncode == 0 and all(checks.values())
    return {
        "ok": ok,
        "prefix": probe.prefix,
        "stage": "done" if ok else "inspect",
        "assembler": as_result.to_dict(),
        "linker": ld_result.to_dict(),
        "readelf": readelf_result.to_dict(),
        "elf_header": header,
        "header_checks": checks,
        "paths": {"asm": str(asm_path), "object": str(obj_path), "elf": str(elf_path)},
        "elf_size": elf_path.stat().st_size if elf_path.exists() else 0,
    }


def path_with_prefix(path: str | Path) -> dict[str, str]:
    p = Path(path).resolve()
    old_path = os.environ.get("PATH", "")
    return {**os.environ, "PATH": f"{p}{os.pathsep}{old_path}"}
