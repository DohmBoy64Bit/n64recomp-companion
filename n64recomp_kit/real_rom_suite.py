from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable

from .audit import elf_symbol_audit, export_functions, filter_ignored_by_export
from .cdb import discover_cdb, write_cdb_evidence
from .config import validate_config
from .doctor import doctor
from .elf import inspect_elf
from .elf_build import build_elf_from_splat, emit_elf_build_helpers, load_elf_build_paths
from .ignore_workflow import scan_unsupported, sync_ignored_toml
from .local_agent import local_llm_ask
from .local_llm_diagnostics import local_llm_doctor
from .local_llm_templates import emit_local_llm_workflow
from .matching import emit_matching_configure, run_configure_min
from .mcp_stdio import McpStdioClient
from .openai_compat import DEFAULT_LLAMA_CPP_BASE_URL, DEFAULT_LMSTUDIO_BASE_URL
from .real_rom_report import (
    EXECUTION_STAGES,
    STATUS_BLOCKED,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIP,
    RealRomSuiteReport,
    SuiteRunner,
    command_coverage,
    command_names,
    format_real_rom_suite,
    utc_now,
    write_markdown,
)
from .real_rom_support import (
    bounded_files,
    discover_single,
    prepare_synthetic_feature_workspace,
    resolve_optional,
    sha256_file,
    slug,
)
from .recomp import run_recomp, summarize_output
from .rom import convert_to_z64, inspect_rom
from .rom_match import rom_build_from_map, rom_match_check, rom_match_sections
from .runtime_template import generate_runtime_project
from .splat import create_splat_config, find_splat, run_splat_config
from .splat_repair import (
    apply_tail_split_hints,
    patch_data_asm,
    patch_tail_asm,
    recompiled_c_sanitize,
    suggest_tail_split_hints,
)
from .toolchain import discover_mips_toolchains, smoke_test_mips_toolchain
from .util import run_command, safe_rmtree, which, write_json
from .workspace import init_function_ledger, init_project_state, scan_workspace

def run_real_rom_suite(
    *,
    rom: str | Path,
    output_dir: str | Path = "build/real-rom-test",
    project_root: str | Path = ".",
    source_root: str | Path | None = None,
    execute: Iterable[str] = (),
    strict: bool = False,
    overwrite: bool = False,
    code_start: int = 0x1000,
    vram: int = 0x80000400,
    splat_config: str | Path | None = None,
    allow_generated_splat: bool = False,
    elf: str | Path | None = None,
    recomp_config: str | Path | None = None,
    n64recomp: str | None = None,
    matching_root: str | Path | None = None,
    runtime_project: str | Path | None = None,
    mips_prefix: str | None = None,
    mupen_root: str | Path | None = None,
    provider: str = "lmstudio",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str = "local",
    timeout: int = 120,
    podman_image: str = "n64recomp-companion:real-rom-test",
) -> RealRomSuiteReport:
    started_wall = utc_now()
    started = time.perf_counter()
    project = Path(project_root).expanduser().resolve()
    rom_path = Path(rom).expanduser().resolve()
    out = Path(output_dir).expanduser()
    if not out.is_absolute():
        out = (project / out).resolve()
    requested = set(execute)
    unknown = requested - EXECUTION_STAGES - {"all"}
    if unknown:
        raise ValueError("unknown execution stage(s): " + ", ".join(sorted(unknown)))
    if "all" in requested:
        requested = set(EXECUTION_STAGES)
    if not rom_path.is_file():
        raise FileNotFoundError(f"ROM file not found: {rom_path}")
    if not project.is_dir():
        raise NotADirectoryError(f"project root is not a directory: {project}")
    if out.exists():
        if not overwrite:
            raise FileExistsError(f"output directory exists: {out}; pass overwrite=True to replace it")
        safe_rmtree(out, protected=[project, rom_path, Path.home()])
    out.mkdir(parents=True)
    runner = SuiteRunner()

    source = resolve_optional(source_root, project) if source_root else Path(__file__).resolve().parents[1]
    supplied_splat = resolve_optional(splat_config, project)
    supplied_elf = resolve_optional(elf, project)
    supplied_recomp = resolve_optional(recomp_config, project)
    supplied_matching = resolve_optional(matching_root, project)
    supplied_runtime = resolve_optional(runtime_project, project)
    supplied_mupen = resolve_optional(mupen_root, project) if mupen_root else None

    rom_info = runner.call(
        "rom.inspect",
        "rom",
        "Inspect the supplied ROM",
        lambda: inspect_rom(rom_path),
        success=lambda value: value.byte_order in {"z64-big-endian", "v64-byte-swapped-16", "n64-little-endian-32"},
        summary=lambda value: f"recognized {value.byte_order} ROM titled {value.title or '<blank>'}",
    )
    if rom_info is None:
        normalized = out / "rom" / "normalized.z64"
    else:
        normalized = out / "rom" / f"{slug(rom_info.title or rom_path.stem)}.z64"
    conversion = runner.call(
        "rom.normalize",
        "rom",
        "Normalize the ROM to big-endian z64 order",
        lambda: convert_to_z64(rom_path, normalized, overwrite=True),
        success=lambda value: value.get("output_byte_order") == "z64-big-endian",
        summary=lambda value: f"wrote {value['size_bytes']} bytes in z64 order",
    )
    runner.call(
        "rom.reinspect",
        "rom",
        "Reinspect the normalized ROM",
        lambda: inspect_rom(normalized),
        success=lambda value: value.byte_order == "z64-big-endian" and value.size_bytes == rom_path.stat().st_size,
        summary=lambda value: f"confirmed z64 order and {value.size_bytes} byte size",
    )

    runner.call(
        "suite.command-registration",
        "suite",
        "Validate CLI command registration",
        lambda: command_names(),
        success=lambda value: sorted(value) == sorted(command_coverage()),
        summary=lambda value: f"registered {len(value)} commands with explicit suite coverage mapping",
        evidence=lambda value: {"commands": value},
    )
    runner.call(
        "workspace.scan",
        "workspace",
        "Scan the project workspace",
        lambda: scan_workspace(project, ignore_dirs=[out.name], max_depth=6),
        summary=lambda value: f"classified workspace as {value.track}, phase {value.phase}",
    )
    isolated_project = out / "generated" / "project-state"
    isolated_project.mkdir(parents=True)
    shutil.copy2(normalized, isolated_project / normalized.name)
    runner.call("workspace.state", "workspace", "Generate an isolated project state file", lambda: init_project_state(isolated_project))
    runner.call("workspace.ledger", "workspace", "Generate an isolated function ledger", lambda: init_function_ledger(isolated_project))

    generated_decomp = out / "generated" / "decomp"
    generated_splat = generated_decomp / "splat.yaml"
    basename = slug((rom_info.title if rom_info else rom_path.stem) or "real_rom")
    runner.call(
        "generated.splat-config",
        "generation",
        "Generate a Splat starting configuration",
        lambda: create_splat_config(
            generated_splat,
            rom_path=normalized,
            basename=basename,
            code_start=code_start,
            vram=vram,
            overwrite=True,
        ),
        summary=lambda value: f"generated {value.config}; boundaries remain evidence-dependent",
    )
    runner.call(
        "generated.matching-configure",
        "generation",
        "Generate the matching-build helper",
        lambda: emit_matching_configure(out / "generated" / "matching", game=basename, overwrite=True),
        summary=lambda value: f"generated {value.path}",
    )
    runner.call(
        "generated.elf-helpers",
        "generation",
        "Generate Windows and Python ELF build helpers",
        lambda: emit_elf_build_helpers(out / "generated" / "elf-helpers", overwrite=True),
        summary=lambda value: f"generated {len(value['files'])} helper files",
    )
    generated_runtime = out / "generated" / "runtime"
    runner.call(
        "generated.runtime-project",
        "generation",
        "Generate the Windows RT64/RmlUi runtime scaffold",
        lambda: generate_runtime_project(generated_runtime, name="RealRomSuiteRuntime", window_title="Real ROM Suite Runtime", overwrite=True),
        summary=lambda value: f"generated {len(value.files)} runtime files",
    )
    generated_llm = out / "generated" / "local-llm"
    runner.call(
        "generated.local-llm-workflow",
        "generation",
        "Generate the local LLM and Mupen64MCP workflow",
        lambda: emit_local_llm_workflow(generated_llm, overwrite=True),
        summary=lambda value: f"generated {len(value.files)} workflow files",
    )

    runner.call(
        "environment.doctor",
        "environment",
        "Collect tool and platform readiness",
        lambda: doctor(n64recomp=n64recomp, root=str(source)),
        summary=lambda value: "recorded native, Podman, Splat, MIPS, N64Recomp, and CDB availability",
    )
    runner.call(
        "environment.toolchain-discovery",
        "environment",
        "Discover MIPS toolchains",
        lambda: [probe.to_dict() for probe in discover_mips_toolchains([mips_prefix] if mips_prefix else None)],
        summary=lambda value: f"found {len(value)} candidate toolchain prefix(es)",
        evidence=lambda value: {"toolchains": value},
    )
    runner.call(
        "debug.cdb-discovery",
        "debug",
        "Discover CDB and project wrappers",
        lambda: discover_cdb(source),
        summary=lambda value: "CDB available" if value.available else "CDB not found; discovery completed",
    )

    synthetic = prepare_synthetic_feature_workspace(out / "synthetic", normalized, vram)
    runner.call(
        "generated.recomp-config",
        "synthetic",
        "Generate and validate a symbol/ROM mode N64Recomp config",
        lambda: validate_config(synthetic["recomp_config"]),
        success=lambda value: value.ok,
        summary=lambda value: f"validation returned {len(value.diagnostics)} diagnostic(s)",
    )
    runner.call(
        "synthetic.asm-repair",
        "synthetic",
        "Exercise assembly scan and repair helpers in an isolated copy",
        lambda: {
            "scan": scan_unsupported(asm_dir=synthetic["asm"], out_dir=out / "synthetic" / "scan").to_dict(),
            "data_patch": patch_data_asm(asm_dir=synthetic["asm"], dry_run=True),
            "tail_patch": patch_tail_asm(asm_dir=synthetic["asm"], dry_run=True),
            "hints": suggest_tail_split_hints(asm_dir=synthetic["asm"], output=out / "synthetic" / "hints.txt"),
            "apply": apply_tail_split_hints(
                yaml_path=synthetic["splat_yaml"],
                hints_file=out / "synthetic" / "hints.txt",
                dry_run=True,
            ),
        },
        success=lambda value: value["scan"]["ok"] and value["data_patch"]["ok"] and value["tail_patch"]["ok"],
        summary=lambda value: "scan, data annotation, duplicate-label repair, hint generation, and YAML application completed",
    )
    runner.call(
        "synthetic.generated-c-sanitize",
        "synthetic",
        "Exercise generated-C sanitation in dry-run mode",
        lambda: recompiled_c_sanitize(path=synthetic["generated_c"], dry_run=True),
        success=lambda value: value.get("ok", False),
        summary=lambda value: f"scanned {value.get('files_scanned', 0)} generated source file(s)",
    )
    runner.call(
        "synthetic.ignore-workflow",
        "synthetic",
        "Exercise ignored-function filtering and TOML synchronization",
        lambda: {
            "filter": filter_ignored_by_export(
                sized_tsv=synthetic["sized"], ignored_files=[synthetic["ignored"]], dry_run=True
            ),
            "sync": sync_ignored_toml(
                config=synthetic["recomp_config"], ignored_files=[synthetic["ignored"]], dry_run=True
            ),
        },
        success=lambda value: value["filter"]["ok"] and value["sync"]["ok"],
        summary=lambda value: "filter and structured TOML synchronization completed without modifying source inputs",
    )

    def rom_match_smoke() -> dict[str, Any]:
        root = out / "synthetic" / "rom-match"
        root.mkdir(parents=True, exist_ok=True)
        expected = root / "expected.bin"
        actual = root / "actual.bin"
        expected.write_bytes(b"REALROMTEST")
        actual.write_bytes(b"REALROMTEST")
        manifest = root / "sections.json"
        manifest.write_text(
            json.dumps(
                {
                    "sections": [
                        {
                            "name": "all",
                            "expected": expected.name,
                            "actual": actual.name,
                            "expected_offset": 0,
                            "actual_offset": 0,
                            "size": expected.stat().st_size,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        part = root / "part.bin"
        part.write_bytes(b"REALROMTEST")
        map_file = root / "map.txt"
        map_file.write_text("0x0 0xB part.bin\n", encoding="utf-8")
        built = root / "built.bin"
        return {
            "match": rom_match_check(expected=expected, actual=actual),
            "sections": rom_match_sections(manifest=manifest),
            "build": rom_build_from_map(map_file=map_file, output=built, root=root),
        }

    runner.call(
        "synthetic.rom-match",
        "synthetic",
        "Exercise ROM matching and map reconstruction helpers",
        rom_match_smoke,
        success=lambda value: value["match"]["ok"] and value["sections"]["ok"] and value["build"]["ok"],
        summary=lambda value: "byte match, section match, and map reconstruction passed",
    )
    runner.call(
        "synthetic.cdb-evidence",
        "synthetic",
        "Write a structured CDB evidence note",
        lambda: write_cdb_evidence(
            out / "synthetic" / "cdb-evidence.md",
            wrapper="suite",
            target="RealRomSuiteRuntime.exe",
            result="INCONCLUSIVE",
            breakpoints=[],
            summary="Local suite exercised evidence-file generation without launching a debugger.",
            overwrite=True,
        ),
        summary=lambda value: f"wrote {value}",
    )

    if "unit-tests" in requested:
        tests_dir = source / "tests"
        if tests_dir.is_dir():
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
            test_env = dict(os.environ)
            test_env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = runner.call(
                "source.unit-tests",
                "source",
                "Run the repository unit and regression suite",
                lambda: run_command(command, cwd=source, timeout=max(timeout, 300), env=test_env),
                success=lambda value: value.returncode == 0,
                summary=lambda value: f"unit-test process exited with code {value.returncode}",
            )
        else:
            runner.blocked("source.unit-tests", "source", "Run the repository unit and regression suite", f"tests directory not found under {source}")
    else:
        runner.skip("source.unit-tests", "source", "Run the repository unit and regression suite", "not requested")

    if "release-check" in requested:
        verifier = source / "scripts" / "verify_release.py"
        if verifier.is_file():
            runner.call(
                "source.release-check",
                "source",
                "Run source-tree release verification",
                lambda: run_command(
                    [sys.executable, str(verifier), "--root", str(source)],
                    cwd=source,
                    timeout=max(timeout, 300),
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                ),
                success=lambda value: value.returncode == 0,
                summary=lambda value: f"release verifier exited with code {value.returncode}",
            )
        else:
            runner.blocked("source.release-check", "source", "Run source-tree release verification", f"release verifier not found under {source}")
    else:
        runner.skip("source.release-check", "source", "Run source-tree release verification", "not requested")

    if "splat" in requested:
        config_for_splat = supplied_splat or generated_splat
        if supplied_splat is None and not allow_generated_splat:
            runner.blocked(
                "external.splat-split",
                "external",
                "Run Splat against the real ROM",
                "the only available config is the broad generated starting config; review it first or pass --allow-generated-splat",
            )
        elif not config_for_splat.is_file():
            runner.blocked("external.splat-split", "external", "Run Splat against the real ROM", f"Splat config not found: {config_for_splat}")
        elif not find_splat():
            runner.blocked("external.splat-split", "external", "Run Splat against the real ROM", "splat command not found")
        else:
            runner.call(
                "external.splat-split",
                "external",
                "Run Splat against the real ROM",
                lambda: run_splat_config(config_for_splat, timeout=timeout),
                success=lambda value: value.get("ok", False),
                summary=lambda value: f"Splat exited with code {value['returncode']}",
            )
    else:
        runner.skip("external.splat-split", "external", "Run Splat against the real ROM", "not requested")

    if "mips" in requested:
        mips_candidates = discover_mips_toolchains([mips_prefix] if mips_prefix else None)
        if not any(candidate.usable_for_elf_smoke for candidate in mips_candidates):
            runner.blocked(
                "external.mips-smoke",
                "external",
                "Assemble and link the MIPS toolchain smoke ELF",
                "no MIPS toolchain with assembler, linker, and readelf was found",
            )
        else:
            runner.call(
                "external.mips-smoke",
                "external",
                "Assemble and link the MIPS toolchain smoke ELF",
                lambda: smoke_test_mips_toolchain(output_dir=out / "external" / "mips-smoke", prefix=mips_prefix, vram=vram),
                success=lambda value: value.get("ok", False),
                summary=lambda value: f"toolchain stage {value.get('stage')} returned {'success' if value.get('ok') else 'failure'}",
            )
    else:
        runner.skip("external.mips-smoke", "external", "Assemble and link the MIPS toolchain smoke ELF", "not requested")

    if "matching" in requested:
        if supplied_matching is None:
            runner.blocked("external.matching-build", "external", "Run the project matching build", "provide --matching-root for a reviewed assembly/linker project")
        elif not (supplied_matching / "configure.py").is_file():
            runner.blocked("external.matching-build", "external", "Run the project matching build", f"configure.py not found under {supplied_matching}")
        else:
            runner.call(
                "external.matching-build",
                "external",
                "Run the project matching build",
                lambda: run_configure_min(supplied_matching, clean=True, build=True, diff=True, timeout=timeout),
                success=lambda value: value.get("ok", False),
                summary=lambda value: f"matching helper exited with code {value['returncode']}",
            )
    else:
        runner.skip("external.matching-build", "external", "Run the project matching build", "not requested")

    project_splat = supplied_splat
    if project_splat is None:
        discovered, ambiguous = discover_single(project, ["splat.yaml", "splat.yml"], exclude=[out])
        project_splat = discovered
        if ambiguous:
            runner.record(
                "project.splat-discovery",
                "project",
                "Discover a project Splat config",
                STATUS_BLOCKED,
                "multiple Splat configs were found; pass --splat-config",
                requested="elf" in requested,
                evidence={"candidates": ambiguous},
            )
    if project_splat and project_splat.is_file():
        try:
            paths = load_elf_build_paths(project_splat, root_path=project)
            asm_exists = Path(paths.asm_path).is_dir() and any(Path(paths.asm_path).rglob("*.s"))
        except Exception:
            asm_exists = False
        if asm_exists:
            runner.call(
                "project.elf-plan",
                "project",
                "Create a dry-run ELF build plan from project Splat output",
                lambda: build_elf_from_splat(project_splat, root_path=project, prefix=mips_prefix, dry_run=True),
                success=lambda value: value.ok,
                summary=lambda value: f"planned {value.object_count} object(s)",
            )
        else:
            runner.skip("project.elf-plan", "project", "Create a dry-run ELF build plan from project Splat output", "project Splat assembly output was not found", requested="elf" in requested)
    else:
        runner.skip("project.elf-plan", "project", "Create a dry-run ELF build plan from project Splat output", "no project Splat config was selected", requested="elf" in requested)

    built_elf: Path | None = None
    if "elf" in requested:
        if project_splat is None or not project_splat.is_file():
            runner.blocked("external.elf-build", "external", "Build the real project ELF", "provide --splat-config or place one unambiguously in the project")
        else:
            result = runner.call(
                "external.elf-build",
                "external",
                "Build the real project ELF",
                lambda: build_elf_from_splat(project_splat, root_path=project, prefix=mips_prefix, clean=True, timeout=timeout),
                success=lambda value: value.ok,
                summary=lambda value: f"linked {value.object_count} object(s) to {value.paths.elf_path}",
            )
            if result is not None and result.ok:
                built_elf = Path(result.paths.elf_path)
    else:
        runner.skip("external.elf-build", "external", "Build the real project ELF", "not requested")

    selected_elf = supplied_elf or built_elf
    if selected_elf is None:
        discovered, ambiguous = discover_single(project, ["*.elf"], exclude=[out])
        selected_elf = discovered
        if ambiguous:
            runner.record(
                "project.elf-discovery",
                "project",
                "Discover a project ELF",
                STATUS_BLOCKED,
                "multiple ELF files were found; pass --elf",
                requested=False,
                evidence={"candidates": ambiguous},
            )
    if selected_elf and selected_elf.is_file():
        runner.call(
            "project.elf-inspect",
            "project",
            "Inspect the selected project ELF",
            lambda: inspect_elf(selected_elf),
            success=lambda value: value.elf_class == "ELF32" and value.endian == "big" and value.machine == "MIPS",
            summary=lambda value: f"identified {value.elf_class} {value.endian}-endian {value.machine}",
        )
        readelf_name = (mips_prefix or "mips-linux-gnu-") + "readelf"
        if which(readelf_name):
            runner.call(
                "project.elf-audit",
                "project",
                "Audit project ELF symbols",
                lambda: elf_symbol_audit(elf=selected_elf, prefix=mips_prefix, alias_policy="warn"),
                success=lambda value: value.get("ok", False),
                summary=lambda value: f"found {value['issue_count']} blocking symbol issue(s) and {value['alias_count']} alias group(s)",
            )
            runner.call(
                "project.elf-export-functions",
                "project",
                "Export sized project ELF functions",
                lambda: export_functions(elf=selected_elf, out_dir=out / "project" / "symbols", prefix=mips_prefix),
                success=lambda value: value.get("ok", False),
                summary=lambda value: f"exported {value['exported_functions']} sized functions",
            )
        else:
            runner.skip("project.elf-audit", "project", "Audit project ELF symbols", f"{readelf_name} not found")
            runner.skip("project.elf-export-functions", "project", "Export sized project ELF functions", f"{readelf_name} not found")
    else:
        runner.skip("project.elf-inspect", "project", "Inspect the selected project ELF", "no project ELF was supplied or discovered")
        runner.skip("project.elf-audit", "project", "Audit project ELF symbols", "no project ELF was supplied or discovered")
        runner.skip("project.elf-export-functions", "project", "Export sized project ELF functions", "no project ELF was supplied or discovered")

    asm_dir: Path | None = None
    if project_splat and project_splat.is_file():
        try:
            asm_dir = Path(load_elf_build_paths(project_splat, root_path=project).asm_path)
        except Exception:
            asm_dir = None
    if asm_dir and asm_dir.is_dir():
        runner.call(
            "project.unsupported-scan",
            "project",
            "Scan project assembly for known unsupported instructions",
            lambda: scan_unsupported(asm_dir=asm_dir, out_dir=out / "project" / "unsupported"),
            summary=lambda value: f"scanned {value.files_scanned} file(s); found {len(value.genuine_ignored)} genuine ignore candidate(s)",
        )
    else:
        runner.skip("project.unsupported-scan", "project", "Scan project assembly for known unsupported instructions", "project assembly directory was not found")

    selected_recomp = supplied_recomp
    if selected_recomp is None:
        candidates = []
        for path in bounded_files(project, ["*.toml"], exclude=[out], max_depth=6):
            try:
                head = path.read_text(encoding="utf-8", errors="replace")[:8192]
            except OSError:
                continue
            if "output_func_path" in head and ("elf_path" in head or "symbols_file_path" in head):
                candidates.append(path.resolve())
        if len(candidates) == 1:
            selected_recomp = candidates[0]
        elif len(candidates) > 1:
            runner.record(
                "project.recomp-discovery",
                "project",
                "Discover a project N64Recomp config",
                STATUS_BLOCKED,
                "multiple N64Recomp TOML files were found; pass --recomp-config",
                requested="recomp" in requested,
                evidence={"candidates": [str(path) for path in sorted(candidates)]},
            )
    if selected_recomp and selected_recomp.is_file():
        runner.call(
            "project.recomp-config",
            "project",
            "Validate the selected N64Recomp config",
            lambda: validate_config(selected_recomp),
            success=lambda value: value.ok,
            summary=lambda value: f"validation returned {len(value.diagnostics)} diagnostic(s)",
        )
    else:
        runner.skip("project.recomp-config", "project", "Validate the selected N64Recomp config", "no project N64Recomp config was supplied or discovered", requested="recomp" in requested)

    if "recomp" in requested:
        if selected_recomp is None or not selected_recomp.is_file():
            runner.blocked("external.recomp-run", "external", "Run N64Recomp on the project", "provide --recomp-config or place one unambiguously in the project")
        else:
            runner.call(
                "external.recomp-run",
                "external",
                "Run N64Recomp on the project",
                lambda: run_recomp(selected_recomp, n64recomp=n64recomp, clean_output=True, timeout=timeout),
                success=lambda value: value.get("status") == "ok",
                summary=lambda value: f"N64Recomp reported status {value.get('status')}",
            )
    else:
        runner.skip("external.recomp-run", "external", "Run N64Recomp on the project", "not requested")

    output_candidates = [project / "RecompiledFuncs"]
    if selected_recomp and selected_recomp.is_file():
        validation = validate_config(selected_recomp, allow_missing_paths=True)
        output_path = validation.resolved_paths.get("input.output_func_path")
        if output_path:
            output_candidates.insert(0, Path(output_path))
    output_path = next((path for path in output_candidates if path.exists()), None)
    if output_path:
        runner.call(
            "project.recomp-summary",
            "project",
            "Summarize generated N64Recomp output",
            lambda: summarize_output(output_path),
            success=lambda value: value.exists,
            summary=lambda value: f"found {value.file_count} generated file(s) totaling {value.total_bytes} bytes",
        )
    else:
        runner.skip("project.recomp-summary", "project", "Summarize generated N64Recomp output", "no generated output directory was found")

    runtime_for_build = supplied_runtime or generated_runtime
    if "runtime" in requested:
        if platform.system() != "Windows":
            runner.blocked("external.runtime-configure", "external", "Configure and build the Windows runtime scaffold", "runtime execution is Windows-only and the current platform is not Windows")
            runner.blocked("external.runtime-build", "external", "Build the Windows runtime scaffold", "runtime execution is Windows-only and the current platform is not Windows")
        elif not which("pwsh"):
            runner.blocked("external.runtime-configure", "external", "Configure and build the Windows runtime scaffold", "pwsh was not found")
            runner.blocked("external.runtime-build", "external", "Build the Windows runtime scaffold", "pwsh was not found")
        else:
            configure_script = runtime_for_build / "scripts" / "Configure-Windows.ps1"
            build_script = runtime_for_build / "scripts" / "Build-Windows.ps1"
            configure = runner.call(
                "external.runtime-configure",
                "external",
                "Configure the Windows runtime scaffold",
                lambda: run_command(["pwsh", "-NoProfile", "-File", str(configure_script)], cwd=runtime_for_build, timeout=max(timeout, 1800)),
                success=lambda value: value.returncode == 0,
                summary=lambda value: f"configure process exited with code {value.returncode}",
            )
            if configure is not None and configure.returncode == 0:
                runner.call(
                    "external.runtime-build",
                    "external",
                    "Build the Windows runtime scaffold",
                    lambda: run_command(["pwsh", "-NoProfile", "-File", str(build_script)], cwd=runtime_for_build, timeout=max(timeout, 1800)),
                    success=lambda value: value.returncode == 0,
                    summary=lambda value: f"build process exited with code {value.returncode}",
                )
            else:
                runner.blocked("external.runtime-build", "external", "Build the Windows runtime scaffold", "runtime configuration did not pass")
    else:
        runner.skip("external.runtime-configure", "external", "Configure the Windows runtime scaffold", "not requested")
        runner.skip("external.runtime-build", "external", "Build the Windows runtime scaffold", "not requested")

    llm_base = base_url or (DEFAULT_LMSTUDIO_BASE_URL if provider == "lmstudio" else DEFAULT_LLAMA_CPP_BASE_URL)
    runner.call(
        "local-llm.doctor",
        "local-llm",
        "Check local LLM and Mupen64MCP layout without live probes",
        lambda: local_llm_doctor(root=generated_llm, mupen_root=supplied_mupen, probe_servers=False),
        summary=lambda value: "recorded workflow scripts, local binaries, and optional Mupen64MCP layout",
    )

    if "mcp" in requested:
        if supplied_mupen is None:
            runner.blocked("external.mcp-tools-list", "external", "Initialize Mupen64MCP and list tools", "provide --mupen-root")
        elif not which("uv"):
            runner.blocked("external.mcp-tools-list", "external", "Initialize Mupen64MCP and list tools", "uv was not found")
        else:
            mcp_python = supplied_mupen / "mcp" / "python"
            if not mcp_python.is_dir():
                runner.blocked("external.mcp-tools-list", "external", "Initialize Mupen64MCP and list tools", f"MCP Python directory not found: {mcp_python}")
            else:
                command = ["uv", "--directory", str(mcp_python), "run", "n64-debug-mcp"]

                def list_tools() -> dict[str, Any]:
                    with McpStdioClient(command, timeout=timeout) as client:
                        tools = client.list_tools()
                    return {"tool_count": len(tools), "tools": [tool.get("name") for tool in tools if tool.get("name")]}

                runner.call(
                    "external.mcp-tools-list",
                    "external",
                    "Initialize Mupen64MCP and list tools",
                    list_tools,
                    success=lambda value: value["tool_count"] > 0,
                    summary=lambda value: f"MCP server exposed {value['tool_count']} tool(s)",
                )
    else:
        runner.skip("external.mcp-tools-list", "external", "Initialize Mupen64MCP and list tools", "not requested")

    if "llm" in requested:
        if not model:
            runner.blocked("external.llm-probe", "external", "Probe a local model for API and tool-call capability", "provide --model")
            runner.blocked("external.llm-completion", "external", "Request a normal completion from the local model", "provide --model")
        else:
            runner.call(
                "external.llm-probe",
                "external",
                "Probe a local model for API and tool-call capability",
                lambda: local_llm_doctor(
                    root=generated_llm,
                    mupen_root=supplied_mupen,
                    lmstudio_base_url=llm_base if provider == "lmstudio" else DEFAULT_LMSTUDIO_BASE_URL,
                    llama_cpp_base_url=llm_base if provider == "llama-cpp" else DEFAULT_LLAMA_CPP_BASE_URL,
                    api_key=api_key,
                    timeout=min(timeout, 30),
                    model=model,
                    model_base_url=llm_base,
                    probe_servers=True,
                ),
                success=lambda value: bool(value.get("tool_call_probe", {}).get("supported")),
                summary=lambda value: "model demonstrated OpenAI-style tool calling" if value.get("tool_call_probe", {}).get("supported") else "server responded but tool-call capability was not demonstrated",
            )
            runner.call(
                "external.llm-completion",
                "external",
                "Request a normal completion from the local model",
                lambda: local_llm_ask(
                    prompt="Reply with a short acknowledgement that the local N64 workflow test request was received.",
                    model=model,
                    base_url=llm_base,
                    api_key=api_key,
                    timeout=min(timeout, 120),
                    mutation_policy="deny",
                ),
                success=lambda value: bool(value.get("ok")) and bool(str(value.get("answer", "")).strip()),
                summary=lambda value: "local model returned a non-empty completion" if str(value.get("answer", "")).strip() else "local model returned an empty completion",
                evidence=lambda value: {
                    "ok": bool(value.get("ok")),
                    "tool_rounds": value.get("tool_rounds"),
                    "answer_length": len(str(value.get("answer", ""))),
                },
            )
    else:
        runner.skip("external.llm-probe", "external", "Probe a local model for API and tool-call capability", "not requested")
        runner.skip("external.llm-completion", "external", "Request a normal completion from the local model", "not requested")

    if "podman" in requested:
        containerfile = source / "Containerfile"
        if not which("podman"):
            runner.blocked("external.podman-build", "external", "Build and smoke-test the Podman image", "podman was not found")
        elif not containerfile.is_file():
            runner.blocked("external.podman-build", "external", "Build and smoke-test the Podman image", f"Containerfile not found under {source}")
        else:
            build_result = runner.call(
                "external.podman-build",
                "external",
                "Build the Podman image",
                lambda: run_command(["podman", "build", "-t", podman_image, "-f", str(containerfile), str(source)], timeout=max(timeout, 3600)),
                success=lambda value: value.returncode == 0,
                summary=lambda value: f"podman build exited with code {value.returncode}",
            )
            if build_result is not None and build_result.returncode == 0:
                runner.call(
                    "external.podman-smoke",
                    "external",
                    "Run the suite CLI inside the Podman image",
                    lambda: run_command(["podman", "run", "--rm", podman_image, "n64recomp-kit", "--help"], timeout=timeout),
                    success=lambda value: value.returncode == 0,
                    summary=lambda value: f"container CLI exited with code {value.returncode}",
                )
            else:
                runner.blocked("external.podman-smoke", "external", "Run the suite CLI inside the Podman image", "Podman image build did not pass")
    else:
        runner.skip("external.podman-build", "external", "Build the Podman image", "not requested")
        runner.skip("external.podman-smoke", "external", "Run the suite CLI inside the Podman image", "not requested")

    counts = {status: sum(check.status == status for check in runner.checks) for status in (STATUS_PASS, STATUS_FAIL, STATUS_BLOCKED, STATUS_SKIP)}
    requested_blocked = any(check.requested and check.status == STATUS_BLOCKED for check in runner.checks)
    failed = counts[STATUS_FAIL] > 0
    complete = counts[STATUS_BLOCKED] == 0 and counts[STATUS_SKIP] == 0
    ok = not failed and (not strict or not requested_blocked)
    rom_payload = rom_info.to_dict() if rom_info is not None else {"path": str(rom_path)}
    rom_payload["sha256"] = sha256_file(rom_path)
    if conversion:
        rom_payload["normalized_path"] = str(normalized)
        rom_payload["normalized_sha256"] = conversion.get("sha256")
    report = RealRomSuiteReport(
        schema_version=1,
        started_at_utc=started_wall,
        finished_at_utc=utc_now(),
        seconds=round(time.perf_counter() - started, 3),
        ok=ok,
        complete=complete,
        strict=strict,
        rom=rom_payload,
        inputs={
            "project_root": str(project),
            "source_root": str(source),
            "splat_config": str(supplied_splat) if supplied_splat else None,
            "elf": str(supplied_elf) if supplied_elf else None,
            "recomp_config": str(supplied_recomp) if supplied_recomp else None,
            "matching_root": str(supplied_matching) if supplied_matching else None,
            "runtime_project": str(supplied_runtime) if supplied_runtime else None,
            "mupen_root": str(supplied_mupen) if supplied_mupen else None,
            "provider": provider,
            "model": model,
            "base_url": llm_base,
        },
        execution_stages=sorted(requested),
        counts=counts,
        checks=runner.checks,
        command_coverage=command_coverage(),
        output_dir=str(out),
    )
    write_json(out / "real-rom-test-report.json", report.to_dict())
    write_markdown(report, out / "real-rom-test-report.md")
    return report

__all__ = ["EXECUTION_STAGES", "RealRomSuiteReport", "format_real_rom_suite", "run_real_rom_suite"]
