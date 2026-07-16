from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from .openai_compat import (
    DEFAULT_LLAMA_CPP_BASE_URL,
    DEFAULT_LMSTUDIO_BASE_URL,
    probe_openai_compatible,
    probe_tool_call_capability,
)


def local_llm_doctor(
    *,
    root: str | Path = ".",
    mupen_root: str | Path | None = None,
    lmstudio_base_url: str = DEFAULT_LMSTUDIO_BASE_URL,
    llama_cpp_base_url: str = DEFAULT_LLAMA_CPP_BASE_URL,
    api_key: str = "local",
    timeout: int = 3,
    model: str | None = None,
    model_base_url: str | None = None,
    probe_servers: bool = True,
) -> dict[str, Any]:
    project_root = Path(root)
    mupen = Path(mupen_root) if mupen_root else None
    scripts = [
        project_root / "scripts" / "Start-Mupen64McpDaemon.ps1",
        project_root / "scripts" / "Start-Mupen64McpServer.ps1",
        project_root / "scripts" / "Invoke-LocalLlmMcpPrompt.ps1",
    ]
    layout: dict[str, Any] = {"root": str(mupen) if mupen else None, "checked": mupen is not None}
    if mupen:
        expected = {
            "daemon": mupen / "native" / "n64_debug_daemon" / "build" / "n64-debug-daemon.exe",
            "mcp_python": mupen / "mcp" / "python",
            "core": mupen / "build" / "mupen64plus" / "lib" / "mupen64plus.dll",
            "input": mupen / "native" / "n64_debug_daemon" / "build" / "mupen64plus-input-inject.dll",
            "rice": mupen / "plugins" / "mupen64plus-video-rice.dll",
            "rsp_hle": mupen / "plugins" / "mupen64plus-rsp-hle.dll",
        }
        layout["paths"] = {name: {"path": str(path), "exists": path.exists()} for name, path in expected.items()}
        layout["ready_for_headless_debug"] = all(layout["paths"][key]["exists"] for key in ["daemon", "mcp_python", "core", "input"])
        layout["ready_for_frame_capture"] = layout["ready_for_headless_debug"] and all(layout["paths"][key]["exists"] for key in ["rice", "rsp_hle"])
    result: dict[str, Any] = {
        "tools": {
            "uv": shutil.which("uv"),
            "lms": shutil.which("lms"),
            "llama-server": shutil.which("llama-server"),
            "python": sys.executable,
        },
        "workflow_scripts": [{"path": str(path), "exists": path.exists()} for path in scripts],
        "mupen64mcp": layout,
    }
    if probe_servers:
        result["lmstudio"] = probe_openai_compatible(lmstudio_base_url, api_key=api_key, timeout=timeout)
        result["llama_cpp"] = probe_openai_compatible(llama_cpp_base_url, api_key=api_key, timeout=timeout)
    else:
        result["lmstudio"] = {"base_url": lmstudio_base_url, "available": False, "skipped": True}
        result["llama_cpp"] = {"base_url": llama_cpp_base_url, "available": False, "skipped": True}
    if model:
        if not probe_servers:
            raise ValueError("model probing requires server probes to be enabled")
        result["tool_call_probe"] = probe_tool_call_capability(
            base_url=model_base_url or lmstudio_base_url,
            api_key=api_key,
            model=model,
            timeout=max(timeout, 10),
        )
    return result


def format_local_llm_doctor(data: dict[str, Any]) -> str:
    lines = ["Local LLM / Mupen64MCP workflow", "Tools:"]
    for name, path in data["tools"].items():
        lines.append(f"  {name:<13} {path or 'not found'}")
    lines.append("Workflow scripts:")
    for script in data["workflow_scripts"]:
        lines.append(f"  {'yes' if script['exists'] else 'no '} {script['path']}")
    mupen = data["mupen64mcp"]
    if mupen.get("checked"):
        lines.append(f"Mupen64MCP root: {mupen['root']}")
        for name, entry in mupen.get("paths", {}).items():
            lines.append(f"  {name:<12} {'yes' if entry['exists'] else 'no '} {entry['path']}")
        lines.append(f"Headless debug ready : {'yes' if mupen.get('ready_for_headless_debug') else 'no'}")
        lines.append(f"Frame capture ready  : {'yes' if mupen.get('ready_for_frame_capture') else 'no'}")
    else:
        lines.append("Mupen64MCP root: not checked")
    for key in ["lmstudio", "llama_cpp"]:
        probe = data[key]
        label = "LM Studio" if key == "lmstudio" else "llama.cpp"
        state = "probe skipped" if probe.get("skipped") else ("available" if probe.get("available") else "not reachable")
        lines.append(f"{label:<10}: {state} at {probe.get('base_url')}")
        if probe.get("models"):
            lines.append("  models: " + ", ".join(probe["models"]))
        elif probe.get("error"):
            lines.append("  " + probe["error"])
    if "tool_call_probe" in data:
        probe = data["tool_call_probe"]
        lines.append(f"Tool calls : {'supported' if probe.get('supported') else 'not demonstrated'} by {probe.get('model')}")
    return "\n".join(lines)
