# End-to-end guide: Starfall 64

This guide uses a fictional game called **Starfall 64**. The names are consistent throughout:

- display name: `Starfall 64`
- project slug: `starfall64`
- ROM basename: `starfall_us`
- normalized ROM: `roms/starfall_us.z64`
- Splat config: `decomp/splat.yaml`
- ELF: `decomp/build/starfall_us.elf`
- N64Recomp config: `decomp/starfall.recomp.toml`
- generated C directory: `RecompiledFuncs`
- host project: `runtime/Starfall64`

The game name, addresses, and file names are examples. The commands are real; segment boundaries and entrypoints must come from the project’s own evidence.

## 1. Create the workspace

```powershell
mkdir starfall64
cd starfall64
mkdir roms, decomp, build, runtime
python -m pip install -e C:\src\n64recomp-companion
python -m n64recomp_kit init-state --root .
python -m n64recomp_kit init-ledger --root .
```

Recommended layout:

```text
starfall64/
  roms/                         local, not committed
  decomp/                       Splat YAML, assembly, symbols, linker script, ELF
  RecompiledFuncs/              N64Recomp output
  runtime/Starfall64/           generated host scaffold and project-owned runtime code
  build/                        JSON reports and temporary evidence
  docs/function_ledger.md
  N64_PROJECT_STATE.md
```

Add ROMs and proprietary assets to the project’s ignore rules.

## 2. Inspect and normalize the ROM

```powershell
python -m n64recomp_kit rom-info roms\starfall_us.z64 --json
```

For a `.v64` or `.n64` source:

```powershell
python -m n64recomp_kit convert-rom source.v64 roms\starfall_us.z64
python -m n64recomp_kit rom-info roms\starfall_us.z64
```

Gate: the inspector must report `z64-big-endian` before the generated Splat workflow is used.


## 2A. Run the safe local suite

Before changing metadata, record a baseline report without launching external tools:

```powershell
python -m n64recomp_kit real-rom-test `
  --rom roms\starfall_us.z64 `
  --project-root . `
  --source-root C:\src\n64recomp-companion `
  --output build\real-rom-test `
  --overwrite
```

Gate: the command returns `PASS`, the ROM checks pass, and the report contains no failed checks. `Complete: no` is normal when external stages were not requested. See [`real-rom-test-suite.md`](real-rom-test-suite.md).

## 3. Install and verify Splat/MIPS tools

Native Python environment:

```powershell
python -m pip install -r C:\src\n64recomp-companion\requirements-decomp.txt
splat --help
python -m n64recomp_kit toolchain-info
python -m n64recomp_kit mips-smoke --output-dir build\mips-smoke
```

Or enter the pinned Podman environment:

```powershell
C:\src\n64recomp-companion\scripts\Enter-PodmanShell.ps1 -WorkDir .
```

Gate: `mips-smoke` must identify ELF32, big-endian MIPS, the requested entrypoint, and MIPS3 flags.

## 4. Initialize Splat

```powershell
python -m n64recomp_kit splat-init `
  --config decomp\splat.yaml `
  --rom roms\starfall_us.z64 `
  --basename starfall_us `
  --code-start 0x1000 `
  --vram 0x80000400 `
  --overwrite
```

The generated config uses splat's built-in ROM analysis: auto-detected entrypoint, compiler, and multi-segment structure (header, IPL3, entry, main with subsegments, tail). Refine it by adding project-evidenced subsegments, pairing `.data`/`.rodata`/`.bss` to text files, and populating `symbols/<game>.symbols.txt`. Re-run `splat-run` iteratively as the config improves.

Run the current Splat CLI:

```powershell
python -m n64recomp_kit splat-run decomp\splat.yaml --report build\splat-report.json
```

The companion invokes `splat split <absolute-config-path>`. Relative child paths are resolved from Splat’s `base_path`.

Gate: Splat exits successfully and creates the expected assembly, symbol, linker-script, and build directories.

## 5. Optional assembly-only ROM match gate

This stage is useful for matching decompilation work. It is not mandatory for every static recompilation project.

```powershell
python -m n64recomp_kit emit-matching-configure --root decomp --game starfall_us --overwrite
Copy-Item roms\starfall_us.z64 decomp\baserom.z64
python -m n64recomp_kit matching-build --root decomp --clean --build --diff --report build\matching-report.json
```

The generated Ninja graph performs:

```text
assembly -> object files -> starfall_us.elf -> objcopy raw binary -> starfall_us.z64
```

Gate: either a byte-for-byte match, or a recorded first mismatch that is attributed to a specific section/symbol boundary.

## 6. Build the N64 ELF

Dry-run first:

```powershell
python -m n64recomp_kit build-elf --config decomp\splat.yaml --root . --dry-run --report build\elf-plan.json
```

Then execute:

```powershell
python -m n64recomp_kit build-elf --config decomp\splat.yaml --root . --clean --report build\elf-build-report.json
python -m n64recomp_kit elf-info decomp\build\starfall_us.elf
```

Gate: the report must show a successful link, `ELF32`, `big` endianness, and `MIPS` machine type.

## 7. Audit symbols and unsupported instructions

```powershell
python -m n64recomp_kit elf-symbol-audit --elf decomp\build\starfall_us.elf --alias-policy warn --report build\elf-symbol-audit.json
python -m n64recomp_kit export-functions --elf decomp\build\starfall_us.elf --out-dir decomp\symbols\recomp
python -m n64recomp_kit scan-unsupported --asm-dir decomp\asm --out-dir decomp\symbols\recomp
```

Use `filter-ignored` before treating an ignore name as a real ELF function. Function aliases are separately classified; choose `allow`, `warn`, or `error` according to project policy.

Gate: zero-size/undefined/overlap issues are understood, and ignored entries refer to actual sized functions unless intentionally documented otherwise.

## 8. Create and validate the N64Recomp config

```powershell
python -m n64recomp_kit init `
  --config decomp\starfall.recomp.toml `
  --entrypoint 0x80000400 `
  --elf build\starfall_us.elf `
  --output-func-path ..\RecompiledFuncs `
  --overwrite

python -m n64recomp_kit check-config decomp\starfall.recomp.toml
```

The checker validates known upstream fields, including structured `mdebug_file_mappings`, and warns on unknown top-level, input, and patch keys so misspellings are visible without blocking forward-compatible additions.

Gate: no error diagnostics. Warnings are reviewed and recorded.

## 9. Run N64Recomp

Native Windows example:

```powershell
python -m n64recomp_kit run decomp\starfall.recomp.toml `
  --n64recomp C:\src\N64Recomp\build\N64Recomp.exe `
  --clean-output `
  --report build\recomp-report.json
```

The runner resolves the config first, uses its directory as the child working directory, and passes only the config filename. Recursive output deletion rejects the filesystem root, home, current project root, and shallow paths.

For a controlled unsupported-function loop:

```powershell
python -m n64recomp_kit recomp-smoke --config decomp\starfall.recomp.toml --n64recomp C:\src\N64Recomp\build\N64Recomp.exe --max-iterations 5 --ignored-file decomp\ignored-extra.txt --report build\recomp-smoke.json
```

Each iteration uses a temporary TOML containing the current ignore set. Review `ignored-extra.txt`, then explicitly apply accepted entries:

```powershell
python -m n64recomp_kit sync-ignored --config decomp\starfall.recomp.toml --ignored decomp\ignored-extra.txt
```

Gate: N64Recomp exits successfully and generated output is summarized.

## 10. Generate the host scaffold

```powershell
python -m n64recomp_kit new-runtime-project `
  --output runtime\Starfall64 `
  --name Starfall64 `
  --window-title "Starfall 64 Recompiled" `
  --overwrite
```

Build the dependency/window layer:

```powershell
cd runtime\Starfall64
.\scripts\Configure-Windows.ps1
.\scripts\Build-Windows.ps1
.\scripts\Run-Windows.ps1
cd ..\..
```

Gate: an SDL window opens. This only proves the host scaffold and dependency resolution. It does not prove RT64 initialization, RmlUi rendering, N64 runtime glue, or execution of recompiled code.

Implement the generated project’s checklist in this order:

1. add N64ModernRuntime or another compatible runtime layer;
2. compile/link `RecompiledFuncs` and required macros;
3. initialize RT64 and connect N64 graphics/runtime data;
4. implement RmlUi interfaces and load `assets/ui/launcher.rml`;
5. route SDL input to UI and game input;
6. add audio, saves, DMA, timing, overlays, and game-specific glue.

## 11. Collect runtime evidence

CDB helpers:

```powershell
python -m n64recomp_kit cdb-info --root runtime\Starfall64
python -m n64recomp_kit cdb-evidence --output build\cdb-evidence.md --wrapper boot --target runtime\Starfall64\build\Starfall64.exe --result INCONCLUSIVE --summary "Boot trace collected; ownership not yet assigned."
```

Mupen64MCP/local model is optional. Keep the agent read-only initially:

```powershell
$env:MUPEN64MCP_ROOT = 'C:\src\Mupen64MCP'
C:\src\n64recomp-companion\scripts\Start-Mupen64McpDaemon.ps1 -Rom $PWD\roms\starfall_us.z64 -Mode Rendered
python -m n64recomp_kit local-llm-doctor --mupen-root $env:MUPEN64MCP_ROOT --model $ModelId --json
```

Do not enable daemon memory writes for normal observation. The local agent’s default mutation policy denies controller, lifecycle/debug-control, unknown, and memory-write tools.

## 12. The workflow loop

For every mismatch, codegen failure, crash, visual issue, or menu issue:

1. **Observe** — collect a focused report, debugger trace, register/memory sample, or framebuffer.
2. **Classify ownership** — Splat metadata, linker/toolchain, N64Recomp TOML, generated-code compiler issue, runtime glue, renderer, UI, or environment.
3. **Change the source of truth** — YAML, linker metadata, symbols, TOML, or project-owned runtime code.
4. **Regenerate the narrowest affected stage** — do not rebuild unrelated layers.
5. **Run the stage gate** — split, ELF audit, ROM match, codegen, host build, or runtime evidence.
6. **Record evidence** — update `N64_PROJECT_STATE.md`, the function ledger, and JSON reports.
7. **Repeat one controlled change at a time.**


At any step, rerun the suite with only the affected external stage. For example, after Splat metadata changes:

```powershell
python -m n64recomp_kit real-rom-test --rom roms\starfall_us.z64 --project-root . --splat-config decomp\splat.yaml --execute splat --strict --overwrite
```

Use [`troubleshooting.md`](troubleshooting.md) to assign failures before editing.
