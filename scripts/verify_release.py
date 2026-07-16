#!/usr/bin/env python3
from __future__ import annotations

import argparse
import argparse as argparse_module
import ast
import json
import re
import shlex
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORT))

from ruamel.yaml import YAML

from n64recomp_kit import __version__
from n64recomp_kit.commands.dispatch import HANDLERS
from n64recomp_kit.commands.parser import COMMAND_DOMAINS, build_parser
from n64recomp_kit.local_llm_templates import emit_local_llm_workflow
from n64recomp_kit.mcp_stdio import MCP_PROTOCOL_VERSION, MCP_SUPPORTED_PROTOCOL_VERSIONS
from n64recomp_kit.runtime_template import generate_runtime_project
from n64recomp_kit.real_rom_report import command_coverage

SKIP_DIRS = {".git", ".deps", ".venv", "build", "dist", "__pycache__", ".pytest_cache"}
GENERATED_DIR_NAMES = {"__pycache__", ".pytest_cache", "dist", "build"}
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TOKEN_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")
FORBIDDEN_WORDS = tuple(word.lower() for word in ("TO" + "DO", "FIX" + "ME", "PLACE" + "HOLDER", "HALLU" + "CINATION"))


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            yield path


def _subparser_commands() -> list[str]:
    parser = build_parser()
    action = next(action for action in parser._actions if isinstance(action, argparse_module._SubParsersAction))
    return sorted(action.choices)


def _check_strict_clean(root: Path, errors: list[str]) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part == ".git" for part in relative.parts):
            continue
        if path.is_dir() and path.name in GENERATED_DIR_NAMES:
            errors.append(f"generated directory present in release tree: {relative}")
        elif path.is_file() and path.suffix in {".pyc", ".pyo"}:
            errors.append(f"generated Python bytecode present in release tree: {relative}")
    word_pattern = re.compile(r"\b(?:" + "|".join(re.escape(word) for word in FORBIDDEN_WORDS) + r")\b", re.IGNORECASE)
    for path in iter_files(root):
        if path.suffix.lower() in {".z64", ".v64", ".n64", ".elf", ".png", ".jpg", ".jpeg", ".webp"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = word_pattern.search(text)
        if match:
            errors.append(f"unfinished-work marker present in {path.relative_to(root)}: {match.group(0)}")


def verify(root: Path, *, strict_clean: bool = False) -> dict:
    result: dict[str, object] = {
        "root": str(root),
        "python_files": 0,
        "json_files": 0,
        "toml_files": 0,
        "yaml_files": 0,
        "markdown_links": 0,
        "cli_commands": 0,
        "documented_cli_examples": 0,
        "runtime_files": 0,
        "local_llm_files": 0,
        "strict_clean": strict_clean,
        "errors": [],
    }
    errors: list[str] = result["errors"]  # type: ignore[assignment]
    yaml = YAML(typ="safe")

    if strict_clean:
        _check_strict_clean(root, errors)

    for path in iter_files(root):
        relative = path.relative_to(root)
        try:
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"), filename=str(relative), feature_version=(3, 11))
                result["python_files"] = int(result["python_files"]) + 1
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
                result["json_files"] = int(result["json_files"]) + 1
            elif path.suffix == ".toml":
                tomllib.loads(path.read_text(encoding="utf-8"))
                result["toml_files"] = int(result["toml_files"]) + 1
            elif path.suffix in {".yaml", ".yml"}:
                yaml.load(path.read_text(encoding="utf-8"))
                result["yaml_files"] = int(result["yaml_files"]) + 1
        except Exception as exc:
            errors.append(f"parse failure in {relative}: {exc}")

        if path.suffix.lower() == ".md":
            text = path.read_text(encoding="utf-8")
            for target in LINK_RE.findall(text):
                target = target.strip()
                if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                result["markdown_links"] = int(result["markdown_links"]) + 1
                resolved = (path.parent / target_path).resolve()
                if not resolved.exists():
                    errors.append(f"broken Markdown link in {relative}: {target}")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    if project_version != __version__:
        errors.append(f"version mismatch: pyproject={project_version}, package={__version__}")

    lock = json.loads((root / "dependencies.lock.json").read_text(encoding="utf-8"))
    direct_dependencies = set(pyproject["project"].get("dependencies", []))
    expected_direct_dependencies = {
        f"tomlkit=={lock['python_dependencies']['tomlkit']}",
        f"ruamel.yaml=={lock['python_dependencies']['ruamel.yaml']}",
    }
    if direct_dependencies != expected_direct_dependencies:
        errors.append("pyproject direct dependencies do not match dependencies.lock.json")
    build_requires = set(pyproject["build-system"].get("requires", []))
    if build_requires != {f"setuptools=={lock['python_build_tools']['setuptools']}"}:
        errors.append("pyproject build backend pin does not match dependencies.lock.json")
    requirements = (root / "requirements-decomp.txt").read_text(encoding="utf-8").splitlines()
    expected_splat = f"splat64[mips]=={lock['python_dependencies']['splat64']}"
    if [line.strip() for line in requirements if line.strip() and not line.lstrip().startswith("#")] != [expected_splat]:
        errors.append("requirements-decomp.txt does not match the locked Splat version")

    sbom = json.loads((root / "sbom.spdx.json").read_text(encoding="utf-8"))
    package = next((p for p in sbom.get("packages", []) if p.get("name") == "n64recomp-companion"), None)
    if not package or package.get("versionInfo") != project_version:
        errors.append("SBOM package version does not match pyproject")
    namespace = str(sbom.get("documentNamespace", ""))
    if not re.fullmatch(r"urn:uuid:[0-9a-fA-F-]{36}", namespace):
        errors.append("SBOM documentNamespace must be a UUID URN")

    commands = _subparser_commands()
    result["cli_commands"] = len(commands)
    suite_coverage = command_coverage()
    if set(suite_coverage) != set(commands):
        errors.append("real-ROM suite command coverage does not match registered CLI commands")
    domain_sets = [set(domain.COMMANDS) for domain in COMMAND_DOMAINS]
    domain_union = set().union(*domain_sets)
    for index, current in enumerate(domain_sets):
        for other in domain_sets[index + 1 :]:
            overlap = sorted(current & other)
            if overlap:
                errors.append("CLI commands owned by multiple domains: " + ", ".join(overlap))
    if domain_union != set(commands):
        errors.append("CLI domain command ownership does not match parser commands")
    if len(HANDLERS) != len(COMMAND_DOMAINS):
        errors.append("CLI handler count does not match command domain count")
    for relative in (
        "docs/real-rom-test-suite.md",
        "scripts/Invoke-RealRomTestSuite.ps1",
        "tools/n64_real_rom_test.py",
    ):
        if not (root / relative).is_file():
            errors.append(f"required real-ROM suite file missing: {relative}")

    docs_paths = sorted(root.rglob("*.md"))
    docs_text = "\n".join(path.read_text(encoding="utf-8") for path in docs_paths)
    undocumented = [command for command in commands if command not in docs_text]
    if undocumented:
        errors.append("commands absent from documentation: " + ", ".join(undocumented))
    parser = build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse_module._SubParsersAction))
    command_options = {
        name: {option for action in command_parser._actions for option in action.option_strings}
        for name, command_parser in subparsers.choices.items()
    }
    example_pattern = re.compile(r"python(?:3)? -m n64recomp_kit\s+([\w-]+)(.*)")
    for path in docs_paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = example_pattern.search(line)
            if not match:
                continue
            command, remainder = match.groups()
            result["documented_cli_examples"] = int(result["documented_cli_examples"]) + 1
            if command not in command_options:
                errors.append(f"unknown documented command in {path.relative_to(root)}:{line_number}: {command}")
                continue
            try:
                tokens = shlex.split(remainder, posix=False)
            except ValueError:
                continue
            for token in tokens:
                if token.startswith("--"):
                    option = token.split("=", 1)[0]
                    if option not in command_options[command]:
                        errors.append(
                            f"unknown documented option in {path.relative_to(root)}:{line_number}: {command} {option}"
                        )

    if (root / "templates").exists():
        errors.append("duplicate top-level runtime template directory exists")

    with tempfile.TemporaryDirectory() as td:
        temp = Path(td)
        runtime = temp / "runtime"
        report = generate_runtime_project(runtime, name="ReleaseAudit", window_title="Release Audit", overwrite=False)
        result["runtime_files"] = len(report.files)
        for path in runtime.rglob("*"):
            if path.is_file() and TOKEN_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                errors.append(f"unresolved runtime token in {path.relative_to(runtime)}")
        manifest = json.loads((runtime / "vcpkg.json").read_text(encoding="utf-8"))
        if manifest.get("builtin-baseline") != lock["source_dependencies"]["vcpkg"]["revision"]:
            errors.append("generated runtime vcpkg baseline does not match dependencies.lock.json")
        rmlui = next((d for d in manifest["dependencies"] if isinstance(d, dict) and d.get("name") == "rmlui"), None)
        if not rmlui or "svg" not in rmlui.get("features", []):
            errors.append("generated runtime does not request the RmlUi svg feature")
        dependencies_cmake = (runtime / "cmake/Dependencies.cmake").read_text(encoding="utf-8")
        rt64_revision = lock["source_dependencies"]["RT64"]["revision"]
        if f"GIT_TAG {rt64_revision}" not in dependencies_cmake or "GIT_SUBMODULES_RECURSE TRUE" not in dependencies_cmake:
            errors.append("generated runtime RT64 fetch does not match the locked revision/submodule policy")
        workflow = temp / "local-llm"
        llm_report = emit_local_llm_workflow(workflow, overwrite=False)
        result["local_llm_files"] = len(llm_report.files)
        root_config = workflow / "configs/local-llm/mupen-root.ps1"
        if root_config.exists() and re.search(r"[A-Za-z]:[\\/]", root_config.read_text(encoding="utf-8", errors="replace")):
            errors.append("default local LLM workflow wrote a machine-specific absolute path")
        checked_in_workflow_files = [
            "scripts/Start-Mupen64McpDaemon.ps1",
            "scripts/Start-Mupen64McpServer.ps1",
            "scripts/Start-LMStudioServer.ps1",
            "scripts/Start-LlamaCppServer.ps1",
            "scripts/Invoke-LocalLlmMcpPrompt.ps1",
            "scripts/Test-LocalLlmMcpWorkflow.ps1",
            "configs/local-llm/mcp-client-config.json",
            "configs/local-llm/local-agent.json",
            "prompts/n64-mcp-analysis.md",
        ]
        for relative in checked_in_workflow_files:
            generated = (workflow / relative).read_bytes()
            checked_in = (root / relative).read_bytes()
            if generated != checked_in:
                errors.append(f"checked-in local LLM workflow file drifted from generator: {relative}")

    for key in ("N64Recomp", "RT64", "Mupen64MCP", "vcpkg"):
        revision = lock["source_dependencies"][key]["revision"]
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            errors.append(f"{key} revision is not a full commit SHA")

    container = (root / "Containerfile").read_text(encoding="utf-8")
    base = lock["container_base"]
    if f"FROM {base['image']}@{base['digest']}" not in container:
        errors.append("Containerfile base image does not match dependencies.lock.json")
    if f"ARG N64RECOMP_REF={lock['source_dependencies']['N64Recomp']['revision']}" not in container:
        errors.append("Containerfile N64Recomp revision does not match dependencies.lock.json")

    mcp_lock = lock.get("mcp_protocol", {})
    if MCP_PROTOCOL_VERSION != mcp_lock.get("preferred_version"):
        errors.append("preferred MCP protocol does not match dependencies.lock.json")
    if set(MCP_SUPPORTED_PROTOCOL_VERSIONS) != set(mcp_lock.get("accepted_versions", [])):
        errors.append("accepted MCP protocols do not match dependencies.lock.json")

    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for action_name, entry in lock["github_actions"].items():
        if f"{action_name}@{entry['revision']}" not in ci:
            errors.append(f"CI action pin for {action_name} does not match dependencies.lock.json")

    result["ok"] = not errors
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify source-tree release consistency without external tool downloads.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--strict-clean", action="store_true", help="also reject generated artifacts and unfinished-work markers")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = verify(Path(args.root).resolve(), strict_clean=args.strict_clean)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("release verification:", "OK" if report["ok"] else "FAILED")
        for key in ("python_files", "json_files", "toml_files", "yaml_files", "markdown_links", "cli_commands", "documented_cli_examples", "runtime_files", "local_llm_files"):
            print(f"  {key}: {report[key]}")
        for error in report["errors"]:
            print("  error:", error)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
