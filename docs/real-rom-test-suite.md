# Real ROM local test suite

`real-rom-test` runs an evidence-producing local test pass against a legally obtained N64 ROM and, when available, the project artifacts built around it.

The suite is deliberately honest about scope. A ROM by itself can prove byte order, header parsing, deterministic normalization, generator behavior, isolated repair helpers, and local tool discovery. It cannot prove correct game segment boundaries, a valid game ELF, successful N64Recomp output, a finished RT64 runtime, or gameplay behavior without the corresponding project files and tools.

## Safe default run

The default run does not start emulators, local models, Podman builds, Splat, a MIPS linker, N64Recomp, or a Windows runtime build.

```powershell
python -m n64recomp_kit real-rom-test `
  --rom C:\roms\starfall_us.z64 `
  --project-root C:\projects\starfall64 `
  --source-root C:\src\n64recomp-companion `
  --output build\real-rom-test `
  --overwrite
```

Equivalent Windows wrapper:

```powershell
C:\src\n64recomp-companion\scripts\Invoke-RealRomTestSuite.ps1 `
  -Rom C:\roms\starfall_us.z64 `
  -ProjectRoot C:\projects\starfall64 `
  -SourceRoot C:\src\n64recomp-companion `
  -Overwrite
```

The safe pass performs these checks in an isolated output directory:

- inspects and hashes the supplied ROM;
- normalizes `.z64`, `.v64`, or `.n64` byte order to a local `.z64` copy;
- reinspects the normalized copy;
- scans the project workspace without treating suite output as project input;
- generates project-state and function-ledger files in an isolated directory;
- generates Splat, matching-build, ELF-helper, RT64/RmlUi runtime, and local-LLM workflow files;
- validates a symbol/ROM-mode N64Recomp configuration against the normalized ROM;
- exercises assembly scanning and repair helpers on synthetic data;
- exercises ignored-function filtering and structured TOML synchronization without changing the project;
- exercises ROM comparison, section comparison, and map reconstruction helpers;
- exercises generated-C sanitation in dry-run mode;
- records toolchain, CDB, Podman, Splat, N64Recomp, local-model, and Mupen64MCP availability;
- writes a command-to-check coverage map for every CLI command.

## Reports

The output directory contains:

```text
build/real-rom-test/
  real-rom-test-report.json
  real-rom-test-report.md
  rom/
  generated/
  synthetic/
  project/
  external/
```

Status meanings are exact:

| Status | Meaning |
|---|---|
| `pass` | The named check executed and met its stated condition. |
| `fail` | The check executed but returned an unsuccessful result or raised an exception. |
| `blocked` | The stage was requested, but a required tool or project artifact was unavailable. |
| `skip` | The stage was not requested or was not applicable to the available project artifacts. |

A normal safe run is expected to be `PASS` while reporting `Complete: no`, because external stages were not requested.

## External execution stages

Use `--execute` once per stage. `--execute all` requests every external stage, but it does not invent missing project metadata or tools.

| Stage | What it executes | Required inputs or environment |
|---|---|---|
| `unit-tests` | Repository unit/regression tests | Companion source tree containing `tests/` |
| `release-check` | Source-tree consistency verifier without clean-archive enforcement | Companion source tree containing `scripts/verify_release.py` |
| `splat` | `splat split` on the selected config | Splat and a reviewed Splat config |
| `mips` | MIPS assembler/linker smoke ELF | GNU-style MIPS toolchain |
| `matching` | Assembly-only build and ROM diff | `--matching-root` with reviewed asm, linker script, `baserom.z64`, and generated helper |
| `elf` | Real MIPS ELF build from Splat output | Reviewed Splat config, generated source/asm, linker script, MIPS toolchain |
| `recomp` | N64Recomp code generation | Valid config and N64Recomp binary |
| `runtime` | Windows runtime configure and build | Windows, PowerShell, Visual Studio/CMake/vcpkg requirements |
| `mcp` | MCP initialize and `tools/list` | Mupen64MCP checkout and `uv` |
| `llm` | Local API tool-call capability probe and normal completion request | Running LM Studio or llama.cpp server and `--model` |
| `podman` | Container image build and CLI smoke | Podman and network access needed by the build |

The suite's `release-check` stage intentionally does not request `verify_release.py --strict-clean`, because importing and testing a source checkout can create local bytecode caches. Clean-archive enforcement remains a separate packaging check run against a fresh extraction.

Use `--strict` when a requested stage must not be blocked:

```powershell
python -m n64recomp_kit real-rom-test `
  --rom C:\roms\starfall_us.z64 `
  --project-root C:\projects\starfall64 `
  --source-root C:\src\n64recomp-companion `
  --execute unit-tests `
  --execute release-check `
  --execute mips `
  --strict `
  --overwrite
```

## Reviewed Splat configuration gate

The suite generates a broad Splat starting configuration to test config generation. It does not assume that the generated segment boundary describes the game correctly.

For a real Splat execution, supply the project’s reviewed configuration:

```powershell
python -m n64recomp_kit real-rom-test `
  --rom C:\roms\starfall_us.z64 `
  --project-root C:\projects\starfall64 `
  --splat-config decomp\splat.yaml `
  --execute splat `
  --strict `
  --overwrite
```

Running Splat against the broad generated config requires the explicit `--allow-generated-splat` switch. That switch confirms only that the operator accepts the potentially large generic split; it does not make the generated layout game-accurate.

## Full Starfall 64 project pass

This fictional example shows how to request the project-backed stages after the project has real metadata and build files:

```powershell
python -m n64recomp_kit real-rom-test `
  --rom C:\roms\starfall_us.z64 `
  --project-root C:\projects\starfall64 `
  --source-root C:\src\n64recomp-companion `
  --splat-config decomp\splat.yaml `
  --elf decomp\build\starfall_us.elf `
  --recomp-config decomp\starfall.recomp.toml `
  --n64recomp C:\src\N64Recomp\build\N64Recomp.exe `
  --matching-root decomp `
  --runtime-project runtime\Starfall64 `
  --mips-prefix mips-linux-gnu- `
  --mupen-root C:\src\Mupen64MCP `
  --provider lmstudio `
  --model $ModelId `
  --execute unit-tests `
  --execute release-check `
  --execute splat `
  --execute mips `
  --execute matching `
  --execute elf `
  --execute recomp `
  --execute runtime `
  --execute mcp `
  --execute llm `
  --strict `
  --overwrite
```

`runtime` configures and builds the Windows scaffold. It does not claim gameplay success because the scaffold still requires project-owned N64ModernRuntime, recompiled-function, RT64, RmlUi, audio, input, save, DMA, timing, and game-specific integration.

`mcp` initializes the MCP server and lists tools. It does not start the emulator daemon or enable memory writes. Start the daemon separately with the project’s reviewed core/plugin paths before performing runtime observations.

`llm` probes the selected local model for OpenAI-style tool-call behavior and sends a separate non-tool completion request. A reachable server with a model that does not demonstrate tool calls, or that returns an empty normal completion, is reported as a failed check rather than silently accepted.

## Using the suite in the workflow loop

Run the safe suite after repository setup, then rerun selected external stages after each source-of-truth change:

```text
observe evidence
  -> classify the owning layer
  -> edit YAML, linker metadata, TOML, or project runtime code
  -> regenerate the narrowest affected stage
  -> run real-rom-test with that stage selected
  -> preserve the JSON and Markdown reports
  -> continue only when the stage gate passes
```

The suite never treats generated `RecompiledFuncs` as the primary source-of-truth edit location and never modifies the supplied ROM.
