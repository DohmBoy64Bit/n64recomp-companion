from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.resources import files
from importlib.abc import Traversable
from pathlib import Path

from .util import atomic_write_text


@dataclass(frozen=True)
class RuntimeProjectReport:
    root: str
    name: str
    slug: str
    window_title: str
    files: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "name": self.name,
            "slug": self.slug,
            "window_title": self.window_title,
            "files": self.files,
            "file_count": len(self.files),
        }


def _slugify(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("project name cannot be empty")
    slug = re.sub(r"[^A-Za-z0-9_+-]+", "-", value).strip("-")
    if not slug:
        raise ValueError("project name must contain at least one alphanumeric character")
    return slug.lower()


def _cmake_identifier(value: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9_]", "_", value)
    ident = re.sub(r"_+", "_", ident).strip("_") or "N64RuntimeStarter"
    return f"N64_{ident}" if ident[0].isdigit() else ident


def _cpp_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", text)))
    if unresolved:
        raise ValueError(f"unresolved runtime template tokens: {', '.join(unresolved)}")
    return text


def generate_runtime_project(
    output: str | Path,
    *,
    name: str,
    window_title: str | None = None,
    overwrite: bool = False,
) -> RuntimeProjectReport:
    out = Path(output)
    slug = _slugify(name)
    title = window_title or f"{name.strip()} Recompiled"
    mapping = {
        "PROJECT_NAME": name.strip(),
        "PROJECT_SLUG": slug,
        "PROJECT_IDENT": _cmake_identifier(name),
        "EXE_NAME": _cmake_identifier(slug),
        "WINDOW_TITLE": title,
        "CPP_WINDOW_TITLE": _cpp_string(title),
    }
    resource_root = files("n64recomp_kit").joinpath("resources/runtime_starter")

    def walk(root: Traversable, prefix: str = "") -> list[tuple[str, Traversable]]:
        items: list[tuple[str, Traversable]] = []
        for child in sorted(root.iterdir(), key=lambda entry: entry.name):
            relative = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                items.extend(walk(child, relative))
            elif child.is_file():
                items.append((relative, child))
        return items

    generated: list[str] = []
    for relative, resource in walk(resource_root):
        destination = out / relative
        if destination.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing file: {destination}")
        text = resource.read_text(encoding="utf-8")
        rendered = _render(text, mapping)
        if destination.suffix.lower() == ".ps1":
            rendered = rendered.replace("\n", "\r\n")
        atomic_write_text(destination, rendered)
        generated.append(relative)
    return RuntimeProjectReport(root=str(out), name=name.strip(), slug=slug, window_title=title, files=generated)
