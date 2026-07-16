from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .util import atomic_write_text

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"
STATUS_BLOCKED = "blocked"

EXECUTION_STAGES = frozenset(
    {
        "unit-tests",
        "release-check",
        "splat",
        "mips",
        "matching",
        "elf",
        "recomp",
        "runtime",
        "mcp",
        "llm",
        "podman",
    }
)


@dataclass
class SuiteCheck:
    check_id: str
    area: str
    title: str
    status: str
    requested: bool
    summary: str
    seconds: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RealRomSuiteReport:
    schema_version: int
    started_at_utc: str
    finished_at_utc: str
    seconds: float
    ok: bool
    complete: bool
    strict: bool
    rom: dict[str, Any]
    inputs: dict[str, Any]
    execution_stages: list[str]
    counts: dict[str, int]
    checks: list[SuiteCheck]
    command_coverage: dict[str, list[str]]
    output_dir: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checks"] = [check.to_dict() for check in self.checks]
        return data


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def json_evidence(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        return converted if isinstance(converted, dict) else {"value": converted}
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple)):
        return {"items": list(value)}
    return {"value": str(value)}


class SuiteRunner:
    def __init__(self) -> None:
        self.checks: list[SuiteCheck] = []

    def record(
        self,
        check_id: str,
        area: str,
        title: str,
        status: str,
        summary: str,
        *,
        requested: bool = True,
        seconds: float = 0.0,
        evidence: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> SuiteCheck:
        check = SuiteCheck(
            check_id=check_id,
            area=area,
            title=title,
            status=status,
            requested=requested,
            summary=summary,
            seconds=round(seconds, 3),
            evidence=evidence or {},
            error=error,
        )
        self.checks.append(check)
        return check

    def call(
        self,
        check_id: str,
        area: str,
        title: str,
        func: Callable[[], Any],
        *,
        requested: bool = True,
        success: Callable[[Any], bool] | None = None,
        summary: Callable[[Any], str] | None = None,
        evidence: Callable[[Any], dict[str, Any]] | None = None,
    ) -> Any | None:
        started = time.perf_counter()
        try:
            value = func()
            passed = success(value) if success else True
            text = summary(value) if summary else ("completed" if passed else "reported an unsuccessful result")
            details = evidence(value) if evidence else json_evidence(value)
            self.record(
                check_id,
                area,
                title,
                STATUS_PASS if passed else STATUS_FAIL,
                text,
                requested=requested,
                seconds=time.perf_counter() - started,
                evidence=details,
            )
            return value
        except Exception as exc:
            self.record(
                check_id,
                area,
                title,
                STATUS_FAIL,
                "execution raised an exception",
                requested=requested,
                seconds=time.perf_counter() - started,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None

    def skip(self, check_id: str, area: str, title: str, reason: str, *, requested: bool = False) -> None:
        self.record(check_id, area, title, STATUS_SKIP, reason, requested=requested)

    def blocked(self, check_id: str, area: str, title: str, reason: str) -> None:
        self.record(check_id, area, title, STATUS_BLOCKED, reason, requested=True)


def command_coverage() -> dict[str, list[str]]:
    return {
        "doctor": ["environment.doctor"],
        "toolchain-info": ["environment.toolchain-discovery"],
        "mips-smoke": ["external.mips-smoke"],
        "workspace-status": ["workspace.scan"],
        "init-state": ["workspace.state"],
        "init-ledger": ["workspace.ledger"],
        "rom-info": ["rom.inspect", "rom.reinspect"],
        "convert-rom": ["rom.normalize"],
        "emit-matching-configure": ["generated.matching-configure"],
        "matching-build": ["external.matching-build"],
        "splat-init": ["generated.splat-config"],
        "splat-run": ["external.splat-split"],
        "patch-data-asm": ["synthetic.asm-repair"],
        "patch-tail-asm": ["synthetic.asm-repair"],
        "tail-split-hints": ["synthetic.asm-repair"],
        "apply-tail-split-hints": ["synthetic.asm-repair"],
        "recompiled-c-sanitize": ["synthetic.generated-c-sanitize"],
        "elf-info": ["project.elf-inspect"],
        "emit-elf-build": ["generated.elf-helpers"],
        "build-elf": ["project.elf-plan", "external.elf-build"],
        "elf-symbol-audit": ["project.elf-audit"],
        "export-functions": ["project.elf-export-functions"],
        "filter-ignored": ["synthetic.ignore-workflow"],
        "mips-link-preflight": ["project.elf-plan"],
        "scan-unsupported": ["project.unsupported-scan"],
        "sync-ignored": ["synthetic.ignore-workflow"],
        "recomp-smoke": ["source.unit-tests"],
        "init": ["generated.recomp-config"],
        "check-config": ["generated.recomp-config", "project.recomp-config"],
        "run": ["external.recomp-run"],
        "summarize-output": ["project.recomp-summary"],
        "batch": ["source.unit-tests"],
        "rom-match-check": ["synthetic.rom-match"],
        "rom-match-sections": ["synthetic.rom-match"],
        "rom-build-from-map": ["synthetic.rom-match"],
        "new-runtime-project": ["generated.runtime-project"],
        "emit-local-llm-workflow": ["generated.local-llm-workflow"],
        "local-llm-doctor": ["local-llm.doctor"],
        "local-llm-ask": ["external.llm-completion"],
        "cdb-info": ["debug.cdb-discovery"],
        "cdb-evidence": ["synthetic.cdb-evidence"],
        "dump-symbols": ["external.splat-split"],
        "real-rom-test": ["suite.command-registration", "rom.inspect", "rom.normalize"],
    }


def command_names() -> list[str]:
    # Imported lazily to keep this report/model module independent of CLI registration.
    from .commands.parser import build_parser

    parser = build_parser()
    action = next(action for action in parser._actions if action.dest == "command")
    return sorted(action.choices)


def write_markdown(report: RealRomSuiteReport, path: Path) -> None:
    lines = [
        "# Real ROM local test suite report",
        "",
        f"- Overall result: **{'PASS' if report.ok else 'FAIL'}**",
        f"- Complete coverage: **{'yes' if report.complete else 'no'}**",
        f"- Strict mode: **{'yes' if report.strict else 'no'}**",
        f"- ROM: `{report.rom.get('path', '')}`",
        f"- ROM SHA-256: `{report.rom.get('sha256', '')}`",
        f"- Output: `{report.output_dir}`",
        "",
        "## Counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status in (STATUS_PASS, STATUS_FAIL, STATUS_BLOCKED, STATUS_SKIP):
        lines.append(f"| {status} | {report.counts.get(status, 0)} |")
    lines.extend(["", "## Checks", "", "| Area | Check | Status | Summary |", "|---|---|---|---|"])
    for check in report.checks:
        detail = check.summary.replace("|", "\\|")
        if check.error:
            detail += f" — {check.error}".replace("|", "\\|")
        lines.append(f"| {check.area} | `{check.check_id}` | **{check.status}** | {detail} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A pass means the named check executed and met its stated condition. A blocked result means the stage was requested but a required tool or project artifact was absent. A skipped result means the stage was not requested or was not applicable. This report does not convert a generic ROM into proven game metadata, a correct ELF, a finished runtime, or validated gameplay by itself.",
            "",
            "## Command coverage",
            "",
            "Each CLI command is mapped to one or more checks. Commands backed only by source unit tests are not represented as real-ROM integration passes unless those unit tests were requested and executed.",
            "",
        ]
    )
    for command, checks in sorted(report.command_coverage.items()):
        lines.append(f"- `{command}`: {', '.join(f'`{item}`' for item in checks)}")
    atomic_write_text(path, "\n".join(lines) + "\n")


def format_real_rom_suite(report: RealRomSuiteReport) -> str:
    lines = [
        f"Status   : {'PASS' if report.ok else 'FAIL'}",
        f"Complete : {'yes' if report.complete else 'no'}",
        f"ROM      : {report.rom.get('path')}",
        f"Output   : {report.output_dir}",
        "Checks   : " + ", ".join(f"{key}={value}" for key, value in report.counts.items()),
        f"JSON     : {Path(report.output_dir) / 'real-rom-test-report.json'}",
        f"Markdown : {Path(report.output_dir) / 'real-rom-test-report.md'}",
    ]
    return "\n".join(lines)
