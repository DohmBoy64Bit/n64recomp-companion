# Splat and MIPS toolchains

## Splat

Use `splat64[mips]` for N64 splitting workflows.

```powershell
.\scripts\Bootstrap-DecompTools.ps1
. .\.deps\decomp-tools\env.ps1
python -m n64recomp_kit splat-run decomp\splat.yaml --report build\splat-report.json
```

The `mips` optional dependency group is required for N64-related platforms. The companion package keeps Splat in a local virtual environment to avoid mixing project tools into the system Python.

## Starting YAML

```powershell
python -m n64recomp_kit splat-init --config decomp\splat.yaml --rom roms\starfall_us.z64 --basename starfall_us --overwrite
```

`splat-init` delegates to splat's built-in `create_config`, which auto-detects the ROM entrypoint, compiler, and a multi-segment structure (header, IPL3, entry code, main code with subsegments, tail bins). The output is post-processed to add toolkit options: `dump_symbols`, `dump_symbols_references`, explicit paths, `disassemble_all`, `find_file_boundaries`, and assembly macro names. If splat is not available, a well-formed fallback template is used instead.

Refine the auto-detected segments with project-specific evidence: add subsegments, pair `.data`/`.rodata`/`.bss` sections to their text files, populate `symbols/<game>.symbols.txt`, and re-run `splat-run` iteratively. See the [splat General Workflow](https://github.com/ethteck/splat/wiki/General-Workflow) for the iterative refinement loop.

## Matching build and ELF boundary

The companion can emit an assembly-only `configure.py`:

```powershell
python -m n64recomp_kit emit-matching-configure --root decomp --game starfall_us --overwrite
```

That helper expects a real linker script, generated `asm/`, and GNU-style MIPS assembler/linker commands. It does not identify the original game compiler and does not replace a mature project build system.

The companion can also build the Splat-configured ELF directly:

```powershell
python -m n64recomp_kit emit-elf-build --root . --overwrite
.\scripts\Build-N64Elf.ps1 -Config decomp\splat.yaml -Root . -Clean -Report build\elf-build-report.json
```

The ELF builder reads `elf_path`, `ld_script_path`, `asm_path`, `src_path`, and `build_path` from Splat YAML. The default `asm-only` profile is intentionally conservative. The `gnu-c` profile exists for projects that already know their C/C++ compiler flags.

## MIPS toolchains

```powershell
python -m n64recomp_kit toolchain-info
python -m n64recomp_kit mips-smoke --prefix mips-linux-gnu-
```

The smoke test assembles a tiny big-endian MIPS object, links it at a VRAM address, and verifies the result with `readelf`. Passing the smoke test only proves the assembler/linker triplet can produce an ELF; it does not prove byte-identical N64 matching output.

## Windows strategy

On Windows, the repeatable path is Podman:

```powershell
.\scripts\Initialize-PodmanMachine.ps1
.\scripts\Build-PodmanImage.ps1
.\scripts\Enter-PodmanShell.ps1 -WorkDir .
```

Native Windows toolchains can be used when a project already has a known compiler/linker setup. The companion discovers MIPS prefixes on `PATH`; it does not ship proprietary IDO binaries or private SDK material.
