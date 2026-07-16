import json
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from n64recomp_kit.local_agent import ToolPolicy, authorize_tool, classify_tool
from n64recomp_kit.mcp_stdio import McpStdioClient
from n64recomp_kit.openai_compat import first_assistant_message


SERVER = r'''
import json, sys, time
mode = sys.argv[1]
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        if mode == "timeout":
            time.sleep(5)
            continue
        for i in range(5000):
            print("diagnostic line %d" % i, file=sys.stderr)
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"protocolVersion":"2025-11-25","capabilities":{},"serverInfo":{"name":"fake","version":"1"}}}), flush=True)
    elif msg.get("method") == "tools/list":
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"tools":[{"name":"n64_get_pc","inputSchema":{"type":"object"}},{"name":"n64_write_memory","inputSchema":{"type":"object"}}]}}), flush=True)
    elif msg.get("method") == "tools/call":
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"content":[{"type":"text","text":"ok"}]}}), flush=True)
'''


class McpSafetyTests(unittest.TestCase):
    def test_tool_categories_and_default_deny(self):
        self.assertEqual(classify_tool("n64_get_pc"), "read-only")
        self.assertEqual(classify_tool("n64_set_controller"), "controller-input")
        self.assertEqual(classify_tool("n64_write_memory"), "memory-write")
        allowed, _ = authorize_tool("n64_get_pc", {}, ToolPolicy())
        denied, reason = authorize_tool("n64_write_memory", {"address": 0}, ToolPolicy())
        self.assertTrue(allowed)
        self.assertFalse(denied)
        self.assertIn("denied", reason)

    def test_allowlist_is_enforced(self):
        policy = ToolPolicy(mutation_policy="allow", allowed_tools=frozenset({"n64_get_pc"}))
        self.assertTrue(authorize_tool("n64_get_pc", {}, policy)[0])
        self.assertFalse(authorize_tool("n64_get_registers", {}, policy)[0])

    def test_empty_choices_error_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, "did not contain an assistant choice"):
            first_assistant_message({"choices": []})

    def test_stdio_timeout_is_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "server.py"
            script.write_text(textwrap.dedent(SERVER), encoding="utf-8")
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                McpStdioClient([sys.executable, str(script), "timeout"], timeout=1).start()
            self.assertLess(time.monotonic() - started, 3)

    def test_stderr_is_drained_while_requests_complete(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "server.py"
            script.write_text(textwrap.dedent(SERVER), encoding="utf-8")
            with McpStdioClient([sys.executable, str(script), "normal"], timeout=5) as client:
                names = [tool["name"] for tool in client.list_tools()]
                self.assertEqual(names, ["n64_get_pc", "n64_write_memory"])
                self.assertTrue(client._stderr_lines)


if __name__ == "__main__":
    unittest.main()
