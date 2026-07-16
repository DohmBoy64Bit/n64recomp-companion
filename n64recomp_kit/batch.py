from __future__ import annotations

import time
import tomllib
from pathlib import Path
from typing import Any

from .config import validate_config
from .recomp import run_recomp


def load_batch(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    with p.open("rb") as f:
        data = tomllib.load(f)
    projects = data.get("project")
    if not isinstance(projects, list):
        raise ValueError("batch manifest must contain one or more [[project]] tables")
    out = []
    for idx, item in enumerate(projects):
        if not isinstance(item, dict):
            raise ValueError(f"project {idx} is not a table")
        name = item.get("name")
        config = item.get("config")
        if not isinstance(name, str) or not name:
            raise ValueError(f"project {idx} has no non-empty name")
        if not isinstance(config, str) or not config:
            raise ValueError(f"project {name} has no non-empty config")
        config_path = Path(config)
        if not config_path.is_absolute():
            config_path = p.parent / config_path
        out.append({"name": name, "config": str(config_path)})
    return out


def run_batch(
    manifest: str | Path,
    *,
    mode: str,
    n64recomp: str | None = None,
    clean_output: bool = False,
    timeout: int | None = None,
    allow_missing_paths: bool = False,
) -> dict[str, Any]:
    projects = load_batch(manifest)
    results = []
    started = time.time()
    for project in projects:
        if mode == "check":
            validation = validate_config(project["config"], allow_missing_paths=allow_missing_paths)
            results.append({"name": project["name"], "config": project["config"], "status": "ok" if validation.ok else "failed", "validation": validation.to_dict()})
        elif mode == "run":
            report = run_recomp(project["config"], n64recomp=n64recomp, clean_output=clean_output, timeout=timeout, allow_missing_paths=allow_missing_paths)
            report["name"] = project["name"]
            results.append(report)
        else:
            raise ValueError("mode must be 'check' or 'run'")
    failed = [r for r in results if r.get("status") != "ok"]
    return {
        "manifest": str(manifest),
        "mode": mode,
        "started_at_unix": int(started),
        "seconds": round(time.time() - started, 3),
        "project_count": len(projects),
        "failed_count": len(failed),
        "ok": len(failed) == 0,
        "results": results,
    }
