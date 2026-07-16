# N64Recomp Companion

A Windows-first workflow toolkit for taking a legally obtained N64 ROM project through **Splat metadata**, a **big-endian MIPS ELF**, **N64Recomp code generation**, and a **host-runtime scaffold**. It also includes readiness audits, ROM matching gates, Podman tooling, CDB evidence helpers, and an optional read-only-by-default Mupen64MCP/local-LLM workflow.

This repository is a workflow and validation toolkit. It does not turn an arbitrary ROM into a finished port automatically, and it does not ship ROMs, game assets, Nintendo SDK material, IDO binaries, model weights, or game-specific runtime code.

## Start here

The complete fictional-project walkthrough is [`docs/end-to-end.md`](docs/end-to-end.md). It uses one game name—**Starfall 64**—from workspace creation through the rebuild/debug loop.

Use this decision table before running commands:

| Goal | Start with | Continue with |
| --- | --- | --- |
| Inspect or normalize a ROM | `rom-info`, `convert-rom` | Splat setup |
| Build matching/disassembly metadata | `splat-init`, `splat-run` | `dump-symbols`, `matching-build`, ELF build |
| Analyze symbol cross-references | `dump-symbols` | Refine subsegments, add symbols |
| Produce the ELF N64Recomp consumes | `build-elf`, `elf-info` | symbol/readiness audit |
| Generate recompilation C | `init`, `check-config`, `run` | `recomp-smoke`, `sync-ignored`, host integration |
| Create a Windows host scaffold | `new-runtime-project` | RT64/RmlUi/runtime implementation |
| Investigate runtime behavior | CDB or Mupen64MCP | evidence loop and source-of-truth fix |
| Repeat work safely across sessions | `init-state`, `init-ledger` | JSON reports and stage gates |
| Test the local workflow against a real ROM | `real-rom-test` | Select external stages only after inputs are ready |

## Windows installation

Requirements:

- Python 3.11, 3.12, or 3.13.
- PowerShell 7 recommended.
- Git, CMake, and Ninja for native source builds.
- Visual Studio 2022 with C++ desktop workload for Windows host projects.
- Podman Desktop or Podman CLI for the reproducible Linux tool environment.

Install the Python package:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m n64recomp_kit doctor --root .
```

Install the Splat extra in the same environment when working on decompilation metadata:

```powershell
python -m pip install -r requirements-decomp.txt
splat --help
```

Detailed native setup: [`docs/windows-setup.md`](docs/windows-setup.md).

## Podman tool environment

The pinned `Containerfile` contains Splat 0.41.0, GNU MIPS tools, and N64Recomp at the revision recorded in `dependencies.lock.json`.

```powershell
.\scripts\Initialize-PodmanMachine.ps1
.\scripts\Build-PodmanImage.ps1
.\scripts\Enter-PodmanShell.ps1 -WorkDir .
```

The image is built from a digest-locked Ubuntu base. Podman details and bind-mount behavior are in [`docs/podman.md`](docs/podman.md).


## Real ROM local test suite

Run the non-destructive local suite against a legally obtained ROM:

```powershell
python -m n64recomp_kit real-rom-test --rom C:\roms\starfall_us.z64 --project-root C:\projects\starfall64 --source-root C:\src\n64recomp-companion --output build\real-rom-test --overwrite
```

The default pass validates the ROM, generators, isolated repair helpers, project discovery, reports, and tool availability. External stages are opt-in through repeated `--execute` arguments. Requested stages that lack a required tool or project artifact are reported as `blocked`; they are never converted into false passes. Use `--strict` when blocked requested stages must fail the command.

Complete usage, output semantics, and the full fictional Starfall 64 invocation are in [`docs/real-rom-test-suite.md`](docs/real-rom-test-suite.md).

## Canonical workflow

```text
ROM inspection
  -> Splat split/refinement
  -> assembly-only match gate when applicable
  -> MIPS ELF build
  -> ELF and symbol readiness audit
  -> N64Recomp TOML validation
  -> N64Recomp C generation
  -> host/runtime build
  -> CDB or Mupen64MCP evidence
  -> fix the owning source of truth
  -> rebuild the narrowest affected stage
```

The loop, exact commands, expected files, and failure ownership are documented in [`docs/end-to-end.md`](docs/end-to-end.md) and [`docs/troubleshooting.md`](docs/troubleshooting.md). The full audit remediation map is in [`docs/audit-remediation.md`](docs/audit-remediation.md).

## Core command groups

### ROM and workspace

```powershell
python -m n64recomp_kit rom-info roms\starfall_us.z64
python -m n64recomp_kit convert-rom input.v64 roms\starfall_us.z64
python -m n64recomp_kit workspace-status --root . --ignore-dir .deps --ignore-dir build
python -m n64recomp_kit init-state --root .
python -m n64recomp_kit init-ledger --root .
```

### Splat and matching

```powershell
python -m n64recomp_kit splat-init --config decomp\splat.yaml --rom roms\starfall_us.z64 --basename starfall_us --overwrite
python -m n64recomp_kit splat-run decomp\splat.yaml --report build\splat-report.json
python -m n64recomp_kit dump-symbols --config decomp\splat.yaml
python -m n64recomp_kit emit-matching-configure --root decomp --game starfall_us --overwrite
python -m n64recomp_kit matching-build --root decomp --clean --build --diff --report build\matching-report.json
```

`splat-init` delegates to splat's built-in `create_config`, which auto-detects the ROM entrypoint, compiler, and multi-segment structure. Refine the output by adding subsegments and symbols iteratively — follow the [splat General Workflow](https://github.com/ethteck/splat/wiki/General-Workflow). Use `dump-symbols` to analyze symbol cross-references between sections.

The generated matching build creates an ELF first, then uses MIPS `objcopy -O binary` to create the raw image compared with `baserom.z64`.

### ELF and toolchain

```powershell
python -m n64recomp_kit toolchain-info
python -m n64recomp_kit mips-smoke --output-dir build\mips-smoke
python -m n64recomp_kit build-elf --config decomp\splat.yaml --root . --clean --report build\elf-build-report.json
python -m n64recomp_kit elf-info decomp\build\starfall_us.elf
python -m n64recomp_kit elf-symbol-audit --elf decomp\build\starfall_us.elf --report build\elf-symbol-audit.json
```

### N64Recomp

```powershell
python -m n64recomp_kit init --config decomp\starfall.recomp.toml --entrypoint 0x80000400 --elf build\starfall_us.elf --output-func-path ..\RecompiledFuncs --overwrite
python -m n64recomp_kit check-config decomp\starfall.recomp.toml
python -m n64recomp_kit run decomp\starfall.recomp.toml --n64recomp .deps\N64Recomp\build\N64Recomp.exe --report build\recomp-report.json
python -m n64recomp_kit summarize-output RecompiledFuncs
python -m n64recomp_kit recomp-smoke --config decomp\starfall.recomp.toml --n64recomp .deps\N64Recomp\build\N64Recomp.exe --max-iterations 5
python -m n64recomp_kit sync-ignored --config decomp\starfall.recomp.toml --ignored decomp\ignored-extra.txt
```

`recomp-smoke` creates temporary TOML files beside the source config and carries newly discovered ignored functions into the next iteration. It does not alter the source TOML unless `sync-ignored` is run explicitly.

### Readiness and repair

The repo includes ELF function export/filtering, unsupported-instruction scans, structured TOML/YAML updates, ROM section checks, MIPS link preflight, assembly repair helpers, and generated-C sanitation. These operations support dry-run/report modes, and mutating repair helpers create backups and use atomic replacement.

See [`docs/readiness-and-repair.md`](docs/readiness-and-repair.md).

### Windows host scaffold

```powershell
python -m n64recomp_kit new-runtime-project --output runtime\Starfall64 --name Starfall64 --window-title "Starfall 64 Recompiled" --overwrite
cd runtime\Starfall64
.\scripts\Configure-Windows.ps1
.\scripts\Build-Windows.ps1
.\scripts\Run-Windows.ps1
```

The generated project is an SDL2 window and dependency scaffold. It requests RmlUi’s `svg` vcpkg feature, links LunaSVG and FreeType, and pins RT64. It deliberately does **not** claim to initialize RT64, create an RmlUi context, run N64ModernRuntime, or execute `RecompiledFuncs`. The generated README lists every integration layer the game project must implement.

See [`docs/runtime-starter.md`](docs/runtime-starter.md).

### Local LLM and Mupen64MCP

Generate or refresh the generalized workflow files, then inspect the environment and run a read-only request:

```powershell
python -m n64recomp_kit emit-local-llm-workflow --root . --overwrite
$env:MUPEN64MCP_ROOT = 'C:\dev\Mupen64MCP'
.\scripts\Start-Mupen64McpDaemon.ps1 -Rom C:\roms\starfall_us.z64 -Mode Rendered
.\scripts\Start-Mupen64McpServer.ps1
python -m n64recomp_kit local-llm-doctor --mupen-root $env:MUPEN64MCP_ROOT --model $ModelId --json
# Offline file/tool check: add --skip-server-probes and omit --model
python -m n64recomp_kit local-llm-ask --provider lmstudio --model $ModelId --mupen-root $env:MUPEN64MCP_ROOT --prompt 'Read status, PC, and registers without changing emulator state.'
```

The local agent exposes read-only tools by default. Controller, lifecycle/debug-control, unknown, and memory-write tools require an explicit mutation policy; an optional allowlist further restricts tool names. Starting the daemon with memory writes enabled is a separate operator decision.

See [`docs/local-llm-mcp.md`](docs/local-llm-mcp.md).

## Direct wrappers

Every `tools/n64_*.py` file delegates to the installed CLI. PowerShell scripts under `scripts/` provide Windows-oriented entry points for setup, Podman, ELF construction, CDB, readiness gates, ROM matching, the real-ROM suite, runtime builds, and local MCP workflows. Core behavior remains in `n64recomp_kit/` so wrappers do not become separate implementations.

## Repository structure

```text
n64recomp_kit/              Python implementation
n64recomp_kit/commands/     CLI parsing and dispatch separation
n64recomp_kit/resources/    Canonical generated runtime project source
scripts/                    Windows, Podman, shell, and CI helpers
tools/                      Thin direct command wrappers
docs/                       End-to-end and topic guides
configs/                    Safe example configuration
prompts/                    Local-agent evidence prompt
tests/                      Unit, regression, and synthetic integration fixtures
Containerfile               Pinned Podman build definition
dependencies.lock.json      Source revision and environment record
THIRD_PARTY.md              Dependency/license matrix
sbom.spdx.json              SPDX package record
```

## Verification

```powershell
python -m unittest discover -s tests -v
bash scripts/check_repo.sh
python scripts/verify_release.py --root . --strict-clean
python -m pip wheel . --no-deps --wheel-dir dist
```

The unit suite includes real-ROM harness coverage, direct-import and blocked-stage behavior, local-model completion probing, and regression coverage for Splat’s `split` subcommand, Splat `base_path` resolution, a successful non-dry-run MIPS ELF path, nested N64Recomp config execution, ELF-to-raw matching output, iterative ignore updates, RmlUi SVG feature selection, safe recursive deletion, malformed map rejection, MCP timeouts, stderr draining, and mutation policy enforcement.

CI definitions additionally cover the declared Python versions on Windows and Ubuntu, PowerShell syntax, shell lint, wheel installation, synthetic Splat/MIPS checks, a pinned N64Recomp source integration, and a Windows no-RT64 runtime build. The Podman image job remains operator-triggered because runner support varies. Local release notes must distinguish tests that ran from workflows that are only defined.

## Scope and evidence boundary

- Use only ROMs and assets you are legally permitted to use.
- A matching ROM build is not required for every N64Recomp project, but a correct ELF/symbol model is required by the selected N64Recomp input mode.
- A generated runtime scaffold is not a finished port.
- Reports describe what the commands observed; they do not prove gameplay correctness without runtime evidence.
- External binaries and services are detected or built at execution time and are not bundled here.

More detail: [`docs/release-verification.md`](docs/release-verification.md), [`docs/legal-and-scope.md`](docs/legal-and-scope.md), [`docs/verified-facts.md`](docs/verified-facts.md), and [`THIRD_PARTY.md`](THIRD_PARTY.md).
