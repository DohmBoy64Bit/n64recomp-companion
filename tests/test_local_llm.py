import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from n64recomp_kit.cli import main
from n64recomp_kit.local_llm import emit_local_llm_workflow, local_llm_doctor, _openai_tools_from_mcp


class LocalLlmWorkflowTests(unittest.TestCase):
    def test_emit_workflow_files(self):
        with tempfile.TemporaryDirectory() as td:
            report = emit_local_llm_workflow(td, mupen_root="C:/Mupen64MCP", overwrite=True)
            files = {Path(p).name for p in report.files}
            self.assertIn("Start-Mupen64McpDaemon.ps1", files)
            self.assertIn("Start-LMStudioServer.ps1", files)
            self.assertIn("Start-LlamaCppServer.ps1", files)
            self.assertIn("Invoke-LocalLlmMcpPrompt.ps1", files)
            cfg = Path(td) / "configs" / "local-llm" / "mcp-client-config.json"
            data = json.loads(cfg.read_text(encoding="utf-8"))
            args = data["mcpServers"]["n64-debug-mcp"]["args"]
            self.assertIn("scripts/Start-Mupen64McpServer.ps1", args)
            self.assertEqual(data["mcpServers"]["n64-debug-mcp"]["env"]["MUPEN64MCP_ROOT"], "${MUPEN64MCP_ROOT}")
            ps = (Path(td) / "scripts" / "Start-Mupen64McpDaemon.ps1").read_text(encoding="utf-8")
            self.assertIn("mupen64plus-video-rice.dll", ps)
            self.assertIn("mupen64plus-rsp-hle.dll", ps)
            self.assertIn("PATH ORDER CRITICAL", ps)

    def test_cli_emit_and_doctor(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(main(["emit-local-llm-workflow", "--root", td, "--mupen-root", "C:/Mupen64MCP", "--overwrite"]), 0)
            self.assertEqual(main(["local-llm-doctor", "--root", td, "--skip-server-probes"]), 0)

    def test_doctor_mupen_layout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in [
                "native/n64_debug_daemon/build/n64-debug-daemon.exe",
                "mcp/python",
                "build/mupen64plus/lib/mupen64plus.dll",
                "native/n64_debug_daemon/build/mupen64plus-input-inject.dll",
                "plugins/mupen64plus-video-rice.dll",
                "plugins/mupen64plus-rsp-hle.dll",
            ]:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                if p.suffix:
                    p.write_bytes(b"x")
                else:
                    p.mkdir(exist_ok=True)
            data = local_llm_doctor(root=".", mupen_root=root, probe_servers=False)
            self.assertTrue(data["mupen64mcp"]["ready_for_headless_debug"])
            self.assertTrue(data["mupen64mcp"]["ready_for_frame_capture"])


    def test_doctor_skip_server_probes(self):
        data = local_llm_doctor(root=".", probe_servers=False)
        self.assertTrue(data["lmstudio"]["skipped"])
        self.assertTrue(data["llama_cpp"]["skipped"])


    def test_cli_provider_and_mupen_root(self):
        with tempfile.TemporaryDirectory() as td:
            mcp_python = Path(td) / "mcp" / "python"
            mcp_python.mkdir(parents=True)
            with patch("n64recomp_kit.commands.local_llm.local_llm_ask", return_value={"ok": True, "answer": "ok"}) as ask:
                rc = main([
                    "local-llm-ask",
                    "--provider", "lmstudio",
                    "--model", "tool-model",
                    "--mupen-root", td,
                    "--prompt", "Read status.",
                ])
            self.assertEqual(rc, 0)
            kwargs = ask.call_args.kwargs
            self.assertEqual(kwargs["base_url"], "http://127.0.0.1:1234/v1")
            self.assertEqual(kwargs["api_key"], "lm-studio")
            self.assertEqual(kwargs["mcp_command"], ["uv", "--directory", str(mcp_python.resolve()), "run", "n64-debug-mcp"])

    def test_cli_rejects_two_mcp_sources(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "mcp" / "python").mkdir(parents=True)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                rc = main([
                    "local-llm-ask",
                    "--model", "tool-model",
                    "--mupen-root", td,
                    "--mcp-command", "uv",
                    "--prompt", "Read status.",
                ])
            self.assertEqual(rc, 1)
            self.assertIn("use either --mupen-root or --mcp-command", stderr.getvalue())

    def test_openai_tools_from_mcp(self):
        tools = _openai_tools_from_mcp([
            {"name": "n64_get_pc", "description": "read pc", "inputSchema": {"type": "object", "properties": {}}}
        ])
        self.assertEqual(tools[0]["function"]["name"], "n64_get_pc")
        self.assertEqual(tools[0]["function"]["parameters"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
