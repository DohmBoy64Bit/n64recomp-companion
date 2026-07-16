from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


def which(name: str) -> str | None:
    return shutil.which(name)


def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: int | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            command=list(command),
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            seconds=round(time.perf_counter() - started, 3),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(
            command=list(command),
            returncode=124,
            stdout=stdout,
            stderr=stderr + f"\nTimed out after {timeout} seconds.",
            seconds=round(time.perf_counter() - started, 3),
        )


def read_bytes(path: str | Path, max_bytes: int | None = None) -> bytes:
    p = Path(path)
    with p.open("rb") as f:
        return f.read() if max_bytes is None else f.read(max_bytes)


def _atomic_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    _atomic_replace(Path(path), data)


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
    _atomic_replace(Path(path), text.encode(encoding))


def backup_file(path: str | Path, *, suffix: str = ".bak") -> Path | None:
    source = Path(path)
    if not source.is_file():
        return None
    candidate = source.with_name(source.name + suffix)
    index = 1
    while candidate.exists():
        candidate = source.with_name(f"{source.name}{suffix}.{index}")
        index += 1
    shutil.copy2(source, candidate)
    return candidate


def write_json(path: str | Path, data: object) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def parse_int(text: str) -> int:
    try:
        return int(text, 0)
    except ValueError as exc:
        raise ValueError(f"invalid integer {text!r}; use decimal or 0x-prefixed hex") from exc


def quote_command(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def is_executable(path: str | Path) -> bool:
    p = Path(path)
    return p.is_file() and os.access(p, os.X_OK)


def python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _contains_path(container: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(container.resolve())
        return True
    except (OSError, ValueError):
        return False


def validate_safe_delete_target(path: str | Path, *, protected: Iterable[str | Path] = ()) -> Path:
    target = Path(path).expanduser().resolve()
    anchor = Path(target.anchor).resolve()
    home = Path.home().resolve()
    cwd = Path.cwd().resolve()
    blocked = [anchor, home, cwd, *(Path(item).expanduser().resolve() for item in protected)]
    if any(_same_path(target, item) or _contains_path(target, item) for item in blocked):
        raise ValueError(f"refusing to recursively delete protected path or its ancestor: {target}")
    if len(target.parts) <= 2:
        raise ValueError(f"refusing to recursively delete shallow path: {target}")
    return target


def safe_rmtree(path: str | Path, *, protected: Iterable[str | Path] = ()) -> None:
    target = validate_safe_delete_target(path, protected=protected)
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"recursive delete target is not a directory: {target}")
        shutil.rmtree(target)
