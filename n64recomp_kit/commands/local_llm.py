from __future__ import annotations

import argparse
from pathlib import Path

from ..local_llm import emit_local_llm_workflow, format_local_llm_doctor, local_llm_ask, local_llm_doctor
from ..util import print_json
from .common import add_json

COMMANDS = {"emit-local-llm-workflow", "local-llm-doctor", "local-llm-ask"}


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("emit-local-llm-workflow", help="write Windows scripts for LM Studio or llama.cpp with Mupen64MCP")
    p.add_argument("--root", default=".", help="repo/project root where scripts and configs are written")
    p.add_argument("--mupen-root", help="optional checkout path written to a local PowerShell environment helper")
    p.add_argument("--overwrite", action="store_true")
    add_json(p)

    p = sub.add_parser("local-llm-doctor", help="check LM Studio, llama.cpp, and Mupen64MCP workflow readiness")
    p.add_argument("--root", default=".")
    p.add_argument("--mupen-root")
    p.add_argument("--lmstudio-base-url", default="http://127.0.0.1:1234/v1")
    p.add_argument("--llama-cpp-base-url", default="http://127.0.0.1:8080/v1")
    p.add_argument("--api-key", default="local")
    p.add_argument("--timeout", type=int, default=3)
    p.add_argument("--model", help="model id to probe for OpenAI-style tool-call support")
    p.add_argument("--model-base-url", help="endpoint used for the optional tool-call probe")
    p.add_argument("--skip-server-probes", action="store_true", help="check files and tools without contacting LM Studio or llama.cpp")
    add_json(p)

    p = sub.add_parser("local-llm-ask", help="send one prompt to a local OpenAI-compatible server, optionally with Mupen64MCP tools")
    p.add_argument("--prompt", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--provider", choices=["lmstudio", "llama-cpp"], default="lmstudio", help="select the default local OpenAI-compatible endpoint")
    p.add_argument("--base-url", help="override the provider endpoint")
    p.add_argument("--api-key", help="override the provider API key")
    p.add_argument("--mupen-root", help="Mupen64MCP checkout; starts its MCP server through uv")
    p.add_argument("--system")
    p.add_argument("--mcp-command", help="MCP server command, such as uv")
    p.add_argument("--mcp-arg", action="append", default=[], help="argument for the MCP command; may be repeated")
    p.add_argument("--max-tool-rounds", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--mutation-policy", choices=["deny", "prompt", "allow"], default="deny")
    p.add_argument("--allow-tool", action="append", default=[], help="restrict MCP exposure to a named tool; may be repeated")
    add_json(p)


def handle(args: argparse.Namespace) -> int | None:
    if args.command not in COMMANDS:
        return None
    if args.command == "emit-local-llm-workflow":
        report = emit_local_llm_workflow(args.root, mupen_root=args.mupen_root, overwrite=args.overwrite)
        if args.json:
            print_json(report.to_dict())
        else:
            print("Wrote local LLM/Mupen64MCP workflow files:")
            for path in report.files:
                print(f"  {path}")
        return 0
    if args.command == "local-llm-doctor":
        data = local_llm_doctor(
            root=args.root,
            mupen_root=args.mupen_root,
            lmstudio_base_url=args.lmstudio_base_url,
            llama_cpp_base_url=args.llama_cpp_base_url,
            api_key=args.api_key,
            timeout=args.timeout,
            model=args.model,
            model_base_url=args.model_base_url,
            probe_servers=not args.skip_server_probes,
        )
        print_json(data) if args.json else print(format_local_llm_doctor(data))
        return 0
    if args.command == "local-llm-ask":
        if args.mupen_root and args.mcp_command:
            raise ValueError("use either --mupen-root or --mcp-command, not both")
        if args.mupen_root:
            mcp_python = (Path(args.mupen_root).expanduser().resolve() / "mcp" / "python")
            if not mcp_python.is_dir():
                raise FileNotFoundError(f"Mupen64MCP Python server directory not found: {mcp_python}")
            command = ["uv", "--directory", str(mcp_python), "run", "n64-debug-mcp"]
        else:
            command = [args.mcp_command] + list(args.mcp_arg or []) if args.mcp_command else None
        default_base = "http://127.0.0.1:1234/v1" if args.provider == "lmstudio" else "http://127.0.0.1:8080/v1"
        default_key = "lm-studio" if args.provider == "lmstudio" else "local"
        data = local_llm_ask(
            prompt=args.prompt,
            model=args.model,
            base_url=args.base_url or default_base,
            api_key=args.api_key or default_key,
            mcp_command=command,
            system=args.system,
            max_tool_rounds=args.max_tool_rounds,
            temperature=args.temperature,
            timeout=args.timeout,
            mutation_policy=args.mutation_policy,
            allowed_tools=args.allow_tool,
        )
        print_json(data) if args.json else print(data.get("answer", ""))
        return 0 if data.get("ok") else 1
    raise AssertionError(f"unhandled local LLM command: {args.command}")
