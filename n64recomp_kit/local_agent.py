from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .mcp_stdio import McpStdioClient
from .openai_compat import chat_completion, first_assistant_message, openai_tools_from_mcp

READ_ONLY_PREFIXES = (
    "n64_get_", "n64_read_", "n64_capture_", "n64_disassemble", "n64_scan_",
    "n64_translate_", "n64_list_", "n64_health_", "n64_rsp_", "n64_pi_",
)
CONTROLLER_TOOLS = {"n64_set_controller", "n64_clear_controller", "n64_inject_input"}
LIFECYCLE_TOOLS = {
    "n64_start_daemon", "n64_stop_daemon", "n64_resume", "n64_pause", "n64_step",
    "n64_set_breakpoint", "n64_remove_breakpoint", "n64_clear_breakpoints", "n64_start_trace", "n64_stop_trace",
}
MEMORY_WRITE_TOOLS = {"n64_write_memory", "n64_write_u8", "n64_write_u16", "n64_write_u32", "n64_write_u64"}
MUTATING_CATEGORIES = {"controller-input", "lifecycle-debug-control", "memory-write", "unknown"}


@dataclass(frozen=True)
class ToolPolicy:
    mutation_policy: str = "deny"
    allowed_tools: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.mutation_policy not in {"deny", "prompt", "allow"}:
            raise ValueError("mutation_policy must be deny, prompt, or allow")


def classify_tool(name: str) -> str:
    if name in MEMORY_WRITE_TOOLS or "write_memory" in name:
        return "memory-write"
    if name in CONTROLLER_TOOLS or "controller" in name or "input" in name:
        return "controller-input"
    if name in LIFECYCLE_TOOLS or any(token in name for token in ("breakpoint", "resume", "pause", "step", "trace")):
        return "lifecycle-debug-control"
    if name.startswith(READ_ONLY_PREFIXES) or name in {"n64_get_status", "n64_get_pc", "n64_get_registers"}:
        return "read-only"
    return "unknown"


def _confirm_tool(name: str, category: str, arguments: dict[str, Any], prompt_fn: Callable[[str], str] | None) -> bool:
    if prompt_fn is None:
        if not sys.stdin.isatty():
            return False
        prompt_fn = input
    answer = prompt_fn(f"Allow {category} MCP tool {name} with arguments {json.dumps(arguments, sort_keys=True)}? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def authorize_tool(
    name: str,
    arguments: dict[str, Any],
    policy: ToolPolicy,
    *,
    prompt_fn: Callable[[str], str] | None = None,
) -> tuple[bool, str]:
    category = classify_tool(name)
    if policy.allowed_tools and name not in policy.allowed_tools:
        return False, f"tool {name} is not in the explicit allowlist"
    if category == "read-only":
        return True, category
    if policy.mutation_policy == "allow":
        return True, category
    if policy.mutation_policy == "prompt" and _confirm_tool(name, category, arguments, prompt_fn):
        return True, category
    return False, f"tool {name} is classified as {category} and was denied because mutation policy is {policy.mutation_policy}"


def tool_result_text(result: dict[str, Any]) -> str:
    content = result.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                parts.append(json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item))
        return "\n".join(parts)
    return json.dumps(result, indent=2, sort_keys=True)


def local_llm_ask(
    *,
    prompt: str,
    model: str,
    base_url: str,
    api_key: str = "local",
    mcp_command: Sequence[str] | None = None,
    system: str | None = None,
    max_tool_rounds: int = 8,
    temperature: float = 0.2,
    timeout: int = 120,
    mutation_policy: str = "deny",
    allowed_tools: Sequence[str] | None = None,
    prompt_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    policy = ToolPolicy(mutation_policy=mutation_policy, allowed_tools=frozenset(allowed_tools or ()))

    if not mcp_command:
        response = chat_completion(
            base_url=base_url, api_key=api_key, model=model, messages=messages,
            tools=None, temperature=temperature, timeout=timeout,
        )
        message = first_assistant_message(response)
        return {"ok": True, "tool_rounds": 0, "answer": message.get("content", ""), "raw": response}

    transcript: list[dict[str, Any]] = []
    with McpStdioClient(mcp_command, timeout=timeout) as mcp:
        mcp_tools = mcp.list_tools()
        exposed = []
        for tool in mcp_tools:
            name = tool.get("name")
            if not isinstance(name, str):
                continue
            category = classify_tool(name)
            if policy.allowed_tools and name not in policy.allowed_tools:
                continue
            if category == "read-only" or policy.mutation_policy in {"prompt", "allow"}:
                exposed.append(tool)
        openai_tools = openai_tools_from_mcp(exposed)
        for round_index in range(max_tool_rounds + 1):
            response = chat_completion(
                base_url=base_url, api_key=api_key, model=model, messages=messages,
                tools=openai_tools, temperature=temperature, timeout=timeout,
            )
            message = first_assistant_message(response)
            tool_calls = message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                raise RuntimeError("local model returned a non-list tool_calls field")
            if not tool_calls:
                return {
                    "ok": True,
                    "tool_rounds": round_index,
                    "answer": message.get("content", ""),
                    "available_mcp_tools": [tool.get("name") for tool in exposed if tool.get("name")],
                    "transcript": transcript,
                }
            messages.append(message)
            for call in tool_calls:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                name = function.get("name")
                raw_args = function.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = None
                if not isinstance(name, str) or not isinstance(arguments, dict):
                    result = {"isError": True, "content": [{"type": "text", "text": "Invalid tool call payload"}]}
                    category = "invalid"
                    authorized = False
                else:
                    authorized, reason = authorize_tool(name, arguments, policy, prompt_fn=prompt_fn)
                    category = classify_tool(name)
                    if authorized:
                        result = mcp.call_tool(name, arguments)
                    else:
                        result = {"isError": True, "content": [{"type": "text", "text": f"Denied by local policy: {reason}"}]}
                transcript.append({"tool": name, "category": category, "authorized": authorized, "arguments": arguments, "result": result})
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": tool_result_text(result)})
    return {"ok": False, "tool_rounds": max_tool_rounds, "answer": "tool round limit reached", "transcript": transcript}
