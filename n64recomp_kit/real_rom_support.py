from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path
from typing import Iterable, Sequence

from .config import create_config

_SKIP_DISCOVERY_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "_deps",
        "packages",
        "installed",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "real_rom"


def resolve_optional(value: str | Path | None, project_root: Path) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def is_within(path: Path, container: Path) -> bool:
    try:
        path.resolve().relative_to(container.resolve())
        return True
    except (OSError, ValueError):
        return False


def bounded_files(
    root: Path,
    patterns: Sequence[str],
    *,
    exclude: Sequence[Path] = (),
    max_depth: int = 6,
) -> Iterable[Path]:
    resolved_root = root.resolve()
    blocked = tuple(path.resolve() for path in exclude)
    for current, dir_names, file_names in os.walk(resolved_root):
        current_path = Path(current)
        depth = len(current_path.relative_to(resolved_root).parts)
        dir_names[:] = sorted(
            name
            for name in dir_names
            if name not in _SKIP_DISCOVERY_DIRS
            and depth < max_depth
            and not any(is_within(current_path / name, item) for item in blocked)
        )
        if any(is_within(current_path, item) for item in blocked):
            dir_names.clear()
            continue
        for name in sorted(file_names):
            if any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
                yield current_path / name


def discover_single(
    root: Path,
    patterns: Sequence[str],
    *,
    exclude: Sequence[Path] = (),
    max_depth: int = 6,
) -> tuple[Path | None, list[str]]:
    unique = sorted({path.resolve() for path in bounded_files(root, patterns, exclude=exclude, max_depth=max_depth)})
    if len(unique) == 1:
        return unique[0], []
    if not unique:
        return None, []
    return None, [str(path) for path in unique]


def prepare_synthetic_feature_workspace(root: Path, normalized_rom: Path, entrypoint: int) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    asm = root / "asm"
    asm.mkdir()
    (asm / "tail_10000.s").write_text(
        "glabel func_80100000\n  trunc.l.d $f0, $f2\nlocal_label:\n  b local_label\n  .word func_80100020\nendlabel\n",
        encoding="utf-8",
    )
    (asm / "tail_20000.s").write_text("local_label:\n  b local_label\n", encoding="utf-8")
    generated_c = root / "generated-c"
    generated_c.mkdir()
    (generated_c / "func.c").write_text("#include <stdint.h>\nvoid func_80100000(void) { }\n", encoding="utf-8")
    splat_yaml = root / "splat.yaml"
    splat_yaml.write_text(
        "segments:\n  - name: tail\n    type: code\n    subsegments:\n      - [0x10000, asm, tail]\n",
        encoding="utf-8",
    )
    symbols = root / "symbols.toml"
    symbols.write_text("[functions]\n", encoding="utf-8")
    recomp_config = root / "synthetic.recomp.toml"
    create_config(
        recomp_config,
        entrypoint=entrypoint,
        elf_path=None,
        rom_path=os.path.relpath(normalized_rom, root),
        symbols_file_path=os.path.relpath(symbols, root),
        output_func_path="RecompiledFuncs",
        overwrite=True,
    )
    sized = root / "sized-funcs.tsv"
    sized.write_text("# vram_hex\tsize\tname\tsection_ndx\tregion\n0x80100000\t16\tfunc_80100000\t1\tmain\n", encoding="utf-8")
    ignored = root / "ignored.txt"
    ignored.write_text("func_80100000\nfunc_80100010\n", encoding="utf-8")
    return {
        "asm": asm,
        "generated_c": generated_c,
        "splat_yaml": splat_yaml,
        "recomp_config": recomp_config,
        "sized": sized,
        "ignored": ignored,
    }
