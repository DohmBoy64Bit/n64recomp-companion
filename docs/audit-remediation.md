# Audit remediation record

This record maps every actionable finding from the previous full-tree audit to the current implementation and its verification evidence. It distinguishes source-level remediation from external integrations that require Windows, Podman, a MIPS cross toolchain, N64Recomp, RT64, or Mupen64MCP.

## Main workflow corrections

| Audit item | v1.8 implementation | Regression evidence |
|---|---|---|
| Splat command form | `splat-run` executes `splat split` with an absolute config path. | `test_splat_uses_split_subcommand`; synthetic Splat job in CI. |
| Splat `base_path` behavior | Config paths follow Splat's base directory semantics. Older generated layouts remain readable for compatibility. | `test_splat_base_path_semantics`. |
| Real ELF success detection | A linked output is accepted only after `inspect_elf` confirms ELF32, big-endian encoding, and MIPS machine type. | `test_real_elf_build_accepts_valid_mips_elf`; `mips-smoke` integration job. |
| Nested N64Recomp config execution | The runner validates the resolved config, changes to its directory, and passes the config filename to N64Recomp. | `test_nested_recomp_config_passes_basename_in_config_directory`. |
| Matching image output | The generated graph links an ELF and then runs MIPS `objcopy -O binary` to create the raw comparison image. Byte comparison is implemented in Python rather than relying on a Unix-only utility. | `test_matching_generator_has_distinct_elf_and_raw_binary_steps`. |
| Iterative recompilation smoke loop | Each run receives a temporary TOML that preserves the source config’s existing ignored functions and adds the currently discovered set. The source TOML changes only through an explicit `sync-ignored` call. | `test_recomp_smoke_uses_updated_iteration_config`; `test_scan_and_sync_ignored`. |
| RmlUi SVG dependency | The vcpkg manifest requests the `rmlui` `svg` feature and includes LunaSVG and FreeType. | `test_runtime_manifest_enables_rmlui_svg_and_pins_rt64`; release verifier. |

## Architecture and ownership

- CLI parsing and dispatch now live under `n64recomp_kit/commands/`; `cli.py` remains the small public entry point. Command ownership is divided into `environment`, `workspace`, `rom`, `elf`, `matching`, `recomp`, `runtime`, `local_llm`, and `debug` modules. Unit tests and the release verifier require those command sets to be complete and non-overlapping.
- The local model workflow is split into OpenAI-compatible HTTP, MCP stdio, agent policy, diagnostics, and generated workflow resources.
- Runtime generation reads one canonical resource tree under `n64recomp_kit/resources/runtime_starter/`. The duplicate checked-in template tree was removed.
- Wrapper scripts remain thin adapters; reusable behavior stays in `n64recomp_kit/`.

The release verifier rejects a duplicate top-level runtime template and checks every generated runtime resource for unresolved generation tokens.

## Documentation and project narrative

- `README.md` is the overview and points directly to the full guide.
- `end-to-end.md` follows one fictional project, **Starfall 64**, from ROM inspection through Splat, matching, ELF construction, N64Recomp, host scaffolding, evidence collection, and the correction loop.
- `troubleshooting.md` assigns failures to the owning stage and identifies the source of truth to change.
- `runtime-starter.md` separates the working SDL/dependency scaffold from game-specific RT64, RmlUi, N64ModernRuntime, audio, input, save, and DMA implementation.
- `local-llm-mcp.md` documents model tool-call capability checks, read-only defaults, mutation controls, and daemon write boundaries.

## Runtime starter scope and reproducibility

The generated Windows project provides:

- CMake/vcpkg configuration;
- an SDL window and event loop;
- pinned RT64 source acquisition with recursive submodules;
- RmlUi with its SVG feature, LunaSVG, and FreeType dependency wiring;
- RML, RCSS, SVG, and launcher/menu assets;
- PowerShell configure, build, and run entry points;
- a project marker used by workspace discovery.

The generated project explicitly lists the game-owned work required to initialize RT64, initialize and render RmlUi, connect N64ModernRuntime or another compatible runtime layer, compile generated functions, and implement game-specific systems. It does not represent those layers as complete.

## Local model and MCP safety

- MCP protocol negotiation accepts the supported versions recorded in `dependencies.lock.json` and prefers the current stable version recorded there.
- Blocking stdio reads use enforceable timeouts.
- Child stderr is continuously drained.
- Malformed model responses with no choices return an explicit error.
- Tool categories are read-only, controller/input, lifecycle/debug-control, memory-write, or unknown.
- Mutation categories are denied by default.
- Optional tool allowlists are enforced before execution.
- Prompt or allow mutation policies require explicit operator selection; prompt mode requires interactive confirmation.
- Generated defaults do not contain a machine-specific Mupen64MCP path.
- The doctor command can probe whether the selected local model produces tool calls, or run an offline file/tool check with `--skip-server-probes`.

## Config, audit, matching, repair, and workspace robustness

- Config validation covers structured `mdebug_file_mappings` and reports unknown top-level, input, and patch keys as warnings.
- Recursive output deletion protects filesystem roots, the user home, the project/config roots, shallow targets, and any ancestor that contains a protected path.
- ELF aliases have an explicit `allow`, `warn`, or `error` policy and are not double-counted as overlaps when they share the same start address.
- ROM section paths resolve relative to the manifest. Empty, malformed, overlapping, and source-short maps fail rather than producing a misleading successful result.
- Mutating TOML and YAML operations use structured parsers. Repair writes use backups and atomic replacement where an existing file is changed.
- Assembly and generated-C repair descriptions match their actual transformations.
- Workspace scanning supports ignored directories, depth bounds, and the `.n64recomp-runtime` marker.
- MIPS smoke verification checks ELF class, byte order, machine, entry point, and architecture flags.

## Testing and release verification

The repository defines:

- unit/regression tests on Windows and Ubuntu for Python 3.11, 3.12, and 3.13;
- wheel build, clean-environment installation, CLI execution, and runtime generation;
- PowerShell parser checks and ShellCheck;
- a real synthetic Splat split and MIPS smoke job;
- a pinned N64Recomp source build and synthetic code-generation run;
- a Windows no-RT64 runtime configure/build job;
- an operator-triggered Podman image build;
- MCP framing, timeout, stderr, response-shape, allowlist, and mutation-policy tests.

`scripts/verify_release.py` parses Python, JSON, TOML, and YAML; checks internal Markdown links; validates version and dependency locks; compares CLI commands with documentation; generates and inspects both runtime and local-model workflows; verifies source/action/container pins; and, in strict mode, rejects generated release artifacts and unfinished-work markers.

## Dependency and supply-chain records

- `dependencies.lock.json` records exact N64Recomp, RT64, Mupen64MCP, and vcpkg revisions, Python package versions, action revisions, MCP protocol versions, and the container digest.
- `Containerfile` uses the recorded Ubuntu digest and N64Recomp revision.
- Generated runtime projects use the recorded vcpkg baseline and RT64 revision.
- `THIRD_PARTY.md` records dependency purpose and license information.
- `sbom.spdx.json` records the package and direct/optional components in SPDX form.

## Verification boundary

Source-level corrections and the Python/synthetic Splat checks can be executed in a Linux development environment. Native PowerShell, Podman, MSVC, a full GNU MIPS link, the pinned N64Recomp build, the RT64-enabled runtime, Mupen64MCP, LM Studio, and llama.cpp require their respective external tools. CI jobs and documented release procedures cover those environments; a local release report must state which of them actually ran rather than treating a workflow definition as execution evidence.
