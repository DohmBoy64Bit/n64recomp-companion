from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Iterable

DEFAULT_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_LLAMA_CPP_BASE_URL = "http://127.0.0.1:8080/v1"


def probe_openai_compatible(base_url: str, *, api_key: str = "local", timeout: int = 5) -> dict[str, Any]:
    base = base_url.rstrip("/")
    request = urllib.request.Request(
        base + "/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body[:1000]}
            models = payload.get("data", []) if isinstance(payload, dict) else []
            return {
                "base_url": base_url,
                "available": True,
                "status": response.status,
                "seconds": round(time.perf_counter() - started, 3),
                "model_count": len(models) if isinstance(models, list) else 0,
                "models": [m.get("id") for m in models if isinstance(m, dict) and m.get("id")][:20],
            }
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {
            "base_url": base_url,
            "available": False,
            "seconds": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def openai_tools_from_mcp(tools: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            continue
        schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {"type": "object", "properties": {}}
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(tool.get("description") or f"Call the MCP tool {name}"),
                    "parameters": schema,
                },
            }
        )
    return converted


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("local model server returned non-JSON content") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("local model server returned a non-object response")
    return decoded


def first_assistant_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        error = response.get("error")
        detail = json.dumps(error, sort_keys=True) if error is not None else "no choices were returned"
        raise RuntimeError(f"local model response did not contain an assistant choice: {detail}")
    first = choices[0]
    if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
        raise RuntimeError("local model response contained an invalid first choice")
    return first["message"]


def probe_tool_call_capability(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = 30,
) -> dict[str, Any]:
    tool = {
        "type": "function",
        "function": {
            "name": "return_probe_token",
            "description": "Return the exact probe token through this function.",
            "parameters": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
                "additionalProperties": False,
            },
        },
    }
    response = chat_completion(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=[{"role": "user", "content": "Call return_probe_token with token N64RECOMP_TOOL_PROBE."}],
        tools=[tool],
        temperature=0.0,
        timeout=timeout,
    )
    message = first_assistant_message(response)
    calls = message.get("tool_calls")
    supported = isinstance(calls, list) and any(
        isinstance(call, dict)
        and isinstance(call.get("function"), dict)
        and call["function"].get("name") == "return_probe_token"
        for call in calls
    )
    return {"supported": supported, "model": model, "tool_call_count": len(calls) if isinstance(calls, list) else 0}
