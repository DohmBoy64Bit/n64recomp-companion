from __future__ import annotations

import platform
import shutil

from .cdb import discover_cdb
from .recomp import find_n64recomp
from .splat import splat_status
from .toolchain import discover_mips_toolchains
from .util import python_version, run_command


def _tool_status(name: str, version_args: list[str] | None = None) -> dict:
    path = shutil.which(name)
    result = {"name": name, "path": path, "available": path is not None}
    if path and version_args:
        cmd = [path] + version_args
        res = run_command(cmd, timeout=10)
        text = (res.stdout or res.stderr).splitlines()
        result["version_probe"] = text[0] if text else ""
        result["version_returncode"] = res.returncode
    return result


def doctor(*, n64recomp: str | None = None, root: str = ".") -> dict:
    binary = find_n64recomp(n64recomp)
    tool_names = [
        ("git", ["--version"]),
        ("cmake", ["--version"]),
        ("ninja", ["--version"]),
        ("python", ["--version"]),
        ("python3", ["--version"]),
        ("py", ["--version"]),
        ("uv", ["--version"]),
        ("podman", ["--version"]),
        ("cl", None),
        ("clang", ["--version"]),
        ("clang++", ["--version"]),
        ("cc", ["--version"]),
        ("c++", ["--version"]),
        ("java", ["-version"]),
        ("mvn", ["--version"]),
    ]
    tools = [_tool_status(name, args) for name, args in tool_names]
    mips = discover_mips_toolchains()
    splat = splat_status()
    cdb = discover_cdb(root)
    tool_map = {tool["name"]: tool for tool in tools}
    has_cmake = tool_map["cmake"]["available"]
    has_generator = tool_map["ninja"]["available"] or tool_map["cl"]["available"]
    has_python = tool_map["python"]["available"] or tool_map["python3"]["available"] or tool_map["py"]["available"]
    return {
        "python": python_version(),
        "platform": platform.platform(),
        "n64recomp": {"path": binary, "available": binary is not None},
        "tools": tools,
        "splat": splat,
        "mips_toolchains": [probe.to_dict() for probe in mips],
        "cdb": cdb.to_dict(),
        "ok_for_windows_native_build": tool_map["git"]["available"] and has_cmake and has_generator and has_python,
        "ok_for_podman_container": tool_map["podman"]["available"],
        "ok_for_decomp_split": splat["available"],
        "ok_for_mips_smoke": any(probe.usable_for_elf_smoke for probe in mips),
    }


def format_doctor(data: dict) -> str:
    lines = [
        f"Python   : {data['python']}",
        f"Platform : {data['platform']}",
        f"N64Recomp: {data['n64recomp']['path'] or 'not found'}",
        f"Splat    : {data['splat']['path'] or 'not found'}",
        f"CDB      : {data['cdb']['path'] or 'not found'}",
        "Tools:",
    ]
    for tool in data["tools"]:
        label = "yes" if tool["available"] else "no"
        line = f"  {tool['name']:<10} {label:<3} {tool['path'] or ''}"
        if tool.get("version_probe"):
            line += f"  {tool['version_probe']}"
        lines.append(line)
    lines.append("MIPS toolchains:")
    if not data.get("mips_toolchains"):
        lines.append("  none found")
    else:
        for chain in data["mips_toolchains"]:
            status = "usable" if chain.get("usable_for_elf_smoke") else "partial"
            compiler = "gcc" if chain.get("has_c_compiler") else "binutils only"
            lines.append(f"  {chain['prefix']} ({status}, {compiler})")
    lines.append("CDB wrappers:")
    lines.extend([f"  {w}" for w in data["cdb"].get("wrappers", [])] or ["  none detected"])
    lines.extend(
        [
            f"Windows native build ready: {'yes' if data['ok_for_windows_native_build'] else 'no'}",
            f"Podman available           : {'yes' if data['ok_for_podman_container'] else 'no'}",
            f"Splat split ready          : {'yes' if data['ok_for_decomp_split'] else 'no'}",
            f"MIPS smoke ready           : {'yes' if data['ok_for_mips_smoke'] else 'no'}",
        ]
    )
    return "\n".join(lines)
