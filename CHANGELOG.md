# Changelog

## [1.10.0] — 2026-07-16

### Changed

- **splat-init: delegates to splat's built-in `create_config`** (`splat.py`).  
  Instead of generating a static template, `splat-init` now runs `splat create_config`
  against the ROM, capturing splat's auto-detected segment structure (entrypoint,
  compiler, subsegments, code/data boundaries, `follows_vram` chains). The output
  is post-processed to add toolkit-specific options (`dump_symbols`, explicit paths,
  `disassemble_all`, macro names) while preserving splat's segment analysis.
  The old template remains as a fallback when splat is unavailable. Config now
  generates multi-segment output (header, IPL3, entry, main, tail bins) instead
  of a single monolithic code segment.

### Added

- **`dump-symbols` command** (`splat.py`, `commands/matching.py`, `real_rom_report.py`).  
  Runs splat with `dump_symbols` + `dump_symbols_references`, parses
  `.splat/splat_symbols.csv`, reports symbol counts by type/subsegment
  and cross-reference statistics. Registered in CLI, test suite, and
  command coverage mapping. CLI command count updated from 42 to 43.

- **Splat hint parsing** (`splat.py`, `commands/matching.py`).  
  `run_splat_config` parses splat's stdout/stderr for file-boundary splits,
  rodata-to-text pairings, and rodata start hints. `splat-run` surfaces hint
  counts in human-readable output. JSON reports include a `hints` field.

### Fixed

- **splat-init: forward-slash paths in generated YAML** (`splat.py`).  
  On Windows, `os.path.relpath` and `Path.__str__` produced backslash paths
  (`"build\\battletanx.elf"`, `"..\\ROM.z64"`) which broke inside the Linux
  Podman container. Now uses `Path.as_posix()` and string literals with `/`.

- **build-elf: space-separated `--asflag` values** (`elf_build.py`).  
  `--asflag "-I /path"` was treated as a single argument `["-I /path"]`,
  causing the assembler to never find include directories. Added
  `shlex.split()`-based `_split_flags()` that splits flag values by
  whitespace, so `-I /work/include` correctly becomes `["-I", "/work/include"]`.

- **build-elf: object path mismatch with splat linker script** (`elf_build.py`).  
  The `_object_path()` helper placed objects under `build/obj/asm/<file>.o`,
  but splat's generated linker script references `build/asm/<file>.o` (no
  `obj/` prefix). Removed the `obj/` prefix so object paths match the linker
  script.

- **emit-matching-configure: missing `-I include` flag** (`matching.py`).  
  The generated `configure.py` used `-EB -mips3` as the default ASFLAGS,
  omitting `-I include`. Splat's assembly files include `macro.inc` via
  `.include "macro.inc"` which requires the include path. The template now
  auto-detects `include/macro.inc` and appends ` -I include` when present.

- **emit-matching-configure: no binary asset rules** (`matching.py`).  
  The generated `configure.py` only handled `.s`/`.S` assembly sources.
  Splat's linker script references binary assets (e.g. `build/assets/ipl3.o`
  for the IPL3 boot block) which need `objcopy` conversion from `.bin` to
  `.o`. The template now parses the linker script for `build/assets/*.o`
  references, finds corresponding `assets/*.bin` files, and generates
  `binobj` Ninja rules using `objcopy -I binary -O elf32-tradbigmips`.

### Documentation

- README: added `dump-symbols` to decision table, updated splat-init description
  to mention `create_config` delegation, added `recomp-smoke`/`sync-ignored`
  to N64Recomp section, linked to splat General Workflow wiki
- AGENTS.md: updated version, command count, limitation notes, testing notes
- `docs/splat-and-toolchain.md`: rewrote Starting YAML section
- `docs/end-to-end.md`: updated Step 4 config description
- `.gitignore`: added `AGENTS.md` (local workspace file, not distributed)

## [1.9.0] — 2026-07-10

Initial release.
