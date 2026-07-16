# Release verification

This repository separates checks that can run from a clean source tree from integrations that require external systems.

## Source-tree checks

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
python scripts/verify_release.py --root .
bash scripts/check_repo.sh
```

A real-ROM safe-suite pass can be added to the source checks without starting external tools:

```powershell
python -m n64recomp_kit real-rom-test --rom C:\roms\starfall_us.z64 --project-root C:\projects\starfall64 --source-root . --output build\real-rom-test --overwrite
```

The suite's optional `release-check` stage runs the consistency verifier without clean-archive enforcement. Use the separate command below against a fresh extraction to prove package cleanliness.

For a clean release tree with generated caches removed:

```powershell
python scripts/verify_release.py --root . --strict-clean
```

The release verifier parses Python, JSON, TOML, and YAML; checks local Markdown links; cross-checks package, SBOM, dependency-lock, container, workflow-action, RT64, vcpkg, Splat, Python, and MCP protocol pins; generates both shipped project workflows; verifies RmlUi SVG selection; checks every CLI command is documented; and rejects generated artifacts or unfinished-work markers in strict mode.

## Package checks

```powershell
python -m pip wheel . --no-deps --wheel-dir dist
python -m venv build\wheel-venv
build\wheel-venv\Scripts\python -m pip install dist\n64recomp_companion-1.9.0-py3-none-any.whl
build\wheel-venv\Scripts\n64recomp-kit --help
build\wheel-venv\Scripts\n64recomp-kit new-runtime-project --output build\wheel-runtime --name WheelRuntime --overwrite
build\wheel-venv\Scripts\n64recomp-kit real-rom-test --rom C:\roms\starfall_us.z64 --project-root build\wheel-suite-project --output suite
```

Confirm the installed wheel can generate `.n64recomp-runtime`, `assets/ui/launcher.rml`, and the complete CMake resource tree. The release archive should be re-extracted into a new directory and the source-tree checks repeated there.

## CI coverage

The checked-in workflow defines:

- Python 3.11, 3.12, and 3.13 unit runs on Windows and Ubuntu;
- PowerShell parsing on Windows and ShellCheck on Linux;
- wheel build, clean installation, and installed-resource generation;
- a real `splat64[mips]` split of a synthetic ROM fixture;
- a GNU MIPS assembler/linker smoke test;
- a pinned N64Recomp source build and synthetic code-generation run;
- a Windows no-RT64 vcpkg/CMake scaffold build;
- an operator-triggered Podman image build.

A workflow definition is not evidence that a particular external job passed. Record the workflow run URL and job result in release notes before claiming those integrations were executed.

## External checks that require operator environments

These cannot be inferred from unit tests:

- Podman Desktop and its Linux machine on Windows;
- Visual Studio/MSVC and the Windows SDK;
- RT64-enabled CMake build and renderer integration;
- Mupen64MCP daemon/plugins;
- LM Studio or llama.cpp with a loaded, tool-capable model;
- a real game-specific Splat project, N64Recomp config, and runtime.

For each external check, preserve command output, dependency versions, and a JSON report or CI job link. Do not promote a dry-run or generated command plan into a successful-build claim.

## Offline local-model workflow check

Use `local-llm-doctor --skip-server-probes` in source-tree verification. This checks generated files and installed commands without depending on local HTTP servers. Model capability probing remains an explicit operator test.
