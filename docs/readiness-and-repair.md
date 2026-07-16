# Readiness, ignore, ROM-match, and Splat repair workflows

This repo includes generalized versions of the high-value archived scripts. They are integrated as `n64recomp-kit` subcommands instead of project-specific one-off files.

## ELF readiness audit

Use this after you have a Splat-built ELF or a saved `readelf -sW` dump.

```powershell
python -m n64recomp_kit elf-symbol-audit --elf decomp\build\starfall_us.elf --report build\elf-symbol-audit.json
python -m n64recomp_kit export-functions --elf decomp\build\starfall_us.elf --out-dir decomp\symbols\recomp --range boot:0x80000400:0x80010000
python -m n64recomp_kit filter-ignored --sized-tsv decomp\symbols\recomp\sized-funcs.tsv --ignored decomp\symbols\recomp\ignored-genuine.txt
```

`elf-symbol-audit` reports zero-size functions, undefined functions, duplicate function addresses, and overlapping sized functions. `export-functions` writes `sized-funcs.tsv`, which can be used as evidence for N64Recomp configs and ignore-list cleanup.

## N64Recomp unsupported-instruction and smoke workflow

```powershell
python -m n64recomp_kit scan-unsupported --asm-dir decomp\asm --out-dir symbols\recomp
python -m n64recomp_kit sync-ignored --config decomp\starfall.recomp.toml --ignored decomp\symbols\recomp\ignored-genuine.txt
python -m n64recomp_kit recomp-smoke --config decomp\starfall.recomp.toml --report build\recomp-smoke-report.json
```

`scan-unsupported` looks for known unsupported instruction patterns in Splat assembly and separates likely genuine ignored functions from functions that merely call low `func_800*` symbols. `sync-ignored` updates `[patches].ignored` without needing hand edits. `recomp-smoke` iterates N64Recomp runs and records failing `func_*` symbols when the tool output exposes them.

## ROM matching gates

```powershell
python -m n64recomp_kit rom-match-check --expected decomp\baserom.z64 --actual decomp\build\starfall_us.z64 --report build\rom-match.json
python -m n64recomp_kit rom-match-sections --manifest config\rom-sections.json --report build\rom-sections.json
python -m n64recomp_kit rom-build-from-map --map decomp\rom-map.txt --output decomp\build\rebuilt.z64
```

A section manifest is JSON:

```json
{
  "sections": [
    {
      "name": "code",
      "expected": "../baserom.z64",
      "actual": "../build/starfall_us.z64",
      "offset": 4096,
      "size": 8192
    }
  ]
}
```

The simple ROM map format is one row per file:

```text
0x000000 0x40 build/header.bin
0x001000 0x2000 build/code.bin
```

## MIPS/Splat link preflight

```powershell
python -m n64recomp_kit mips-link-preflight --config decomp\splat.yaml
python -m n64recomp_kit mips-link-preflight --config decomp\splat.yaml --execute --report build\mips-link-preflight.json
```

Without `--execute`, the command dry-runs the assembler/linker commands generated from the Splat YAML. With `--execute`, it delegates to the repo ELF builder and requires the MIPS toolchain to be installed or available through the selected environment.

## Advanced Splat repair helpers

These commands are opt-in and report what they changed.

```powershell
python -m n64recomp_kit patch-data-asm --asm-dir decomp\asm --dry-run --json
python -m n64recomp_kit patch-tail-asm --asm-dir decomp\asm --dry-run --json
python -m n64recomp_kit tail-split-hints --asm-dir decomp\asm --output symbols\tail\split-hints.txt
python -m n64recomp_kit apply-tail-split-hints --yaml decomp\splat.yaml --hints symbols\tail\split-hints.txt --dry-run
python -m n64recomp_kit recompiled-c-sanitize --path RecompiledFuncs --dry-run
```

`patch-data-asm` annotates `.word func_*` data-pointer references for review. `patch-tail-asm` renames duplicate non-function labels across tail assembly files. `tail-split-hints` and `apply-tail-split-hints` help carry split-boundary evidence into a Splat YAML.

## Windows helper scripts

```powershell
.\scripts\Invoke-RecompReadiness.ps1 -SplatYaml decomp\splat.yaml -AsmDir decomp\asm -RecompToml decomp\starfall.recomp.toml -DryRun
.\scripts\Invoke-RomMatchGate.ps1 -Expected decomp\baserom.z64 -Actual decomp\build\starfall_us.z64
```

The PowerShell wrappers call the Python commands and keep paths Windows-friendly.
