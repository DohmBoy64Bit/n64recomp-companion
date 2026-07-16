# Failure ownership and troubleshooting

Use the first failing stage to choose the owner. Avoid patching downstream output when the source problem is upstream.

| Symptom | Likely owner | First checks | Source of truth to change |
|---|---|---|---|
| ROM byte order rejected | ROM preparation | `rom-info` | normalized local ROM copy |
| Splat exits before output | Splat YAML/segments | `splat-run` report, `base_path`, segment ranges | `splat.yaml` |
| Assembly does not build | generated asm or MIPS toolchain | `mips-link-preflight`, assembler stderr | Splat boundaries/symbols or toolchain flags |
| Linker reports undefined/overlap | ELF/linker metadata | linker map, `elf-symbol-audit` | linker script, symbol files, Splat metadata |
| ELF inspector reports wrong class/endian/machine | toolchain/profile | `mips-smoke`, `elf-info` | toolchain selection and flags |
| ROM matching fails | section layout/content | first mismatch and section manifest | Splat segmentation, linker layout, source/asm |
| Config checker errors | N64Recomp TOML | exact diagnostic key | `.recomp.toml` |
| N64Recomp rejects one function | instruction/function metadata | `scan-unsupported`, `recomp-smoke` | Splat function boundary, patch policy, TOML |
| Generated C does not compile | generated-code/runtime contract | compiler error and generated function | runtime macros/includes first; source metadata if generation is wrong |
| Host starts but no game code executes | runtime integration | generated scaffold checklist | project-owned runtime and entrypoint glue |
| Black framebuffer in MCP | daemon renderer mode | Rice/RSP paths, daemon arguments | daemon startup configuration |
| RT64 target missing | dependency fetch/config | CMake configure log, pinned revision | runtime CMake/dependency config |
| SVG does not render in RmlUi | RmlUi integration/feature | vcpkg `rmlui[svg]`, plugin/context initialization | vcpkg manifest and project-owned RmlUi setup |
| Font does not render | RmlUi/FreeType setup/assets | font path and font-engine initialization | project-owned UI initialization/assets |
| Local model chats but never calls tools | model/server capability | `local-llm-doctor --model` | choose a tool-capable model/template/server config |
| MCP mutation is denied | local safety policy | tool category, allowlist, mutation policy | explicit operator invocation, not model prompt text |
| Workspace phase is wrong | scan bounds/markers | `--ignore-dir`, `--max-depth`, `.n64recomp-runtime` | project marker/layout or scan arguments |

## Safe repair rules

- Run dry-run mode before a repair command when available.
- Keep generated assembly and generated C reproducible from their upstream inputs.
- Structured TOML/YAML operations create backups before replacing an existing file.
- Recursive clean operations reject protected or shallow targets.
- Review ignored functions; an ignore list is a compatibility policy, not proof that code is unnecessary.
- Treat aliases according to explicit project policy rather than automatically calling them errors.
- Keep memory writes disabled during observation-only MCP sessions.
