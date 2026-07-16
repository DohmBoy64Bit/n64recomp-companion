#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$ROOT"
python3 -m unittest discover -s tests -v
python3 -m n64recomp_kit doctor --json >/dev/null || true
python3 -m n64recomp_kit workspace-status --root . --ignore-dir .deps --ignore-dir build >/dev/null
python3 -m n64recomp_kit check-config tests/fixtures/valid_elf_config.toml >/dev/null
python3 -m n64recomp_kit elf-info tests/fixtures/minimal_mips_be.elf >/dev/null
python3 -m n64recomp_kit rom-info tests/fixtures/minimal.z64 >/dev/null
python3 -m n64recomp_kit emit-matching-configure --root "$TMP/matching" --game check_game --overwrite >/dev/null
python3 -m n64recomp_kit emit-elf-build --root "$TMP/elf" --overwrite >/dev/null
python3 -m n64recomp_kit cdb-info --root . --json >/dev/null || true
python3 -m n64recomp_kit new-runtime-project --output "$TMP/runtime" --name CheckRuntime --overwrite --json >/dev/null
python3 -m n64recomp_kit emit-local-llm-workflow --root "$TMP/local-llm" --overwrite >/dev/null
python3 -m n64recomp_kit local-llm-doctor --root "$TMP/local-llm" --skip-server-probes --json >/dev/null
python3 - "$ROOT/tests/fixtures/minimal.z64" "$TMP/real-rom.z64" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes() + b"\0" * 0x2000)
PY
mkdir -p "$TMP/real-rom-project"
python3 -m n64recomp_kit real-rom-test --rom "$TMP/real-rom.z64" --project-root "$TMP/real-rom-project" --source-root "$ROOT" --output suite >/dev/null
python3 scripts/verify_release.py --root .
