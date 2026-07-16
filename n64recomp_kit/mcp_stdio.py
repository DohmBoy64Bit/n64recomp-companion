from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any, Sequence

from . import __version__

MCP_PROTOCOL_VERSION = "2025-11-25"
MCP_SUPPORTED_PROTOCOL_VERSIONS = frozenset({"2025-11-25", "2025-06-18", "2025-03-26"})


class McpStdioClient:
    """Line-delimited JSON-RPC MCP client with enforceable read timeouts."""

    def __init__(self, command: Sequence[str], *, cwd: str | Path | None = None, timeout: int = 30):
        if not command:
            raise ValueError("MCP command cannot be empty")
        self.command = list(command)
        self.cwd = str(cwd) if cwd is not None else None
        self.timeout = timeout
        self.proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_lines: deque[str] = deque(maxlen=200)
        self._threads: list[threading.Thread] = []
        self.protocol_version: str | None = None

    def __enter__(self) -> "McpStdioClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _pump_stdout(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            self._stdout_queue.put(line)
        self._stdout_queue.put(None)

    def _pump_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for line in self.proc.stderr:
            self._stderr_lines.append(line.rstrip())

    def start(self) -> None:
        if self.proc is not None:
            return
        self.proc = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._threads = [
            threading.Thread(target=self._pump_stdout, name="mcp-stdout", daemon=True),
            threading.Thread(target=self._pump_stderr, name="mcp-stderr", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        try:
            initialized = self.request(
                "initialize",
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "n64recomp-kit-local-llm", "version": __version__},
                },
            )
            negotiated = initialized.get("protocolVersion")
            if not isinstance(negotiated, str) or negotiated not in MCP_SUPPORTED_PROTOCOL_VERSIONS:
                raise RuntimeError(f"MCP server selected unsupported protocol version: {negotiated!r}")
            self.protocol_version = negotiated
            self.notify("notifications/initialized", {})
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        proc = self.proc
        if proc is None:
            return
        if proc.stdin:
            try:
                proc.stdin.close()
            except OSError:
                pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        for stream in (proc.stdout, proc.stderr):
            if stream:
                try:
                    stream.close()
                except OSError:
                    pass
        for thread in self._threads:
            thread.join(timeout=0.2)
        self._threads.clear()
        self.proc = None

    def _send(self, payload: dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("MCP process is not running")
        self.proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        if self.proc is None:
            raise RuntimeError("MCP process is not running")
        while True:
            try:
                line = self._stdout_queue.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise TimeoutError(f"timed out after {self.timeout}s waiting for MCP response") from exc
            if line is None:
                stderr = "\n".join(self._stderr_lines)
                raise RuntimeError(f"MCP process exited with {self.proc.poll()}: {stderr}")
            text = line.strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                return message

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        while True:
            message = self._read_message()
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"MCP {method} failed: {message['error']}")
            result = message.get("result", {})
            return result if isinstance(result, dict) else {"result": result}

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def list_tools(self) -> list[dict[str, Any]]:
        tools = self.request("tools/list").get("tools", [])
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments})
