#!/usr/bin/env bash
set -euo pipefail
PREFIX_ARG=()
OUT="build/mips-smoke"
if [ "$#" -gt 0 ]; then
  PREFIX_ARG=(--prefix "$1")
fi
python3 -m n64recomp_kit mips-smoke "${PREFIX_ARG[@]}" --output-dir "$OUT"
