# N64Recomp workflow

N64Recomp is best treated as a static code generator inside a larger project. The companion toolkit separates the workflow into evidence layers so fixes land in the right place.

## Track A: matching decompilation

| Phase | Goal | Companion commands |
|---|---|---|
| 0 - ROM recon | Record byte order, hashes, header fields, entrypoint hints | `rom-info`, `convert-rom`, `init-state` |
| 1 - Splat | Generate YAML and split ROM into assembly/data artifacts | `splat-init`, `splat-run`, `dump-symbols` |
| 2 - First asm match | Build from generated assembly and compare against baserom | `emit-matching-configure`, `matching-build` |
| 3 - ELF handoff | Assemble/link Splat output into the ELF used by N64Recomp | `emit-elf-build`, `build-elf`, `elf-info` |
| 4 - Discovery | Record function boundaries and confidence | `init-ledger`, `workspace-status` |
| 5 - Runtime block | Identify libultra or custom MMIO/runtime layer | `elf-info`, `toolchain-info` |
| 5 - C migration | Convert selected functions to C only after boundaries are stable | external project build tools |

Generated `asm/` is disposable. BSS, segment, overlay, and split fixes go into Splat YAML or symbol metadata, not generated assembly.

## Track B: N64Recomp static port

| Phase | Goal | Companion commands |
|---|---|---|
| B0 - Metadata clean | Confirm ROM, Splat YAML, symbols, overlays, and function ledger quality | `workspace-status`, `elf-info`, `check-config`, `dump-symbols` |
| B1 - Codegen | Produce recompilation C/C++ output | `run`, `summarize-output`, `batch` |
| B2 - Runtime | Wire librecomp/host runtime, overlays, DMA, saves, input, audio | project runtime build |
| B3 - Renderer/host | Bring up renderer, audio, input, save paths, packaging | CDB and project runtime logs |
| B4 - Polish | Launcher, UI, options, release automation | project-specific scripts |

Generated `RecompiledFuncs/` is disposable output. Fix TOML, symbols, overlays, or runtime glue before editing generated code.

## Workspace classifier

```powershell
python -m n64recomp_kit workspace-status --root .
```

The classifier reports the likely track, phase, missing artifacts, and one next action. It is intentionally conservative. A project with `RecompiledFuncs/` and no runtime folder is marked as runtime integration rather than complete.

## Reports

Every command that runs an external tool can write JSON:

```powershell
python -m n64recomp_kit splat-run decomp\splat.yaml --report build\splat-report.json
python -m n64recomp_kit run decomp\starfall.recomp.toml --report build\recomp-report.json
python -m n64recomp_kit matching-build --build --report build\matching-build.json
python -m n64recomp_kit build-elf --config decomp\splat.yaml --root . --report build\elf-build-report.json
```

Keep these reports with issue notes so future fixes are evidence-backed.

## Readiness gates after ELF generation

After Splat produces assembly and the ELF build helper can dry-run, run the added readiness gates:

```powershell
python -m n64recomp_kit mips-link-preflight --config decomp\splat.yaml
python -m n64recomp_kit scan-unsupported --asm-dir decomp\asm --out-dir decomp\symbols\recomp
python -m n64recomp_kit sync-ignored --config decomp\starfall.recomp.toml --ignored decomp\symbols\recomp\ignored-genuine.txt
python -m n64recomp_kit elf-symbol-audit --elf decomp\build\starfall_us.elf --report build\elf-symbol-audit.json
python -m n64recomp_kit export-functions --elf decomp\build\starfall_us.elf --out-dir decomp\symbols\recomp
python -m n64recomp_kit rom-match-check --expected decomp\baserom.z64 --actual decomp\build\starfall_us.z64
```

These commands make the Splat output, MIPS ELF, N64Recomp config, and ROM reconstruction evidence easier to validate before moving into runtime integration.
