#!/usr/bin/env bash
set -euo pipefail

PREFIX="$PWD/.deps/N64Recomp"
REF="ffb39cdad1da5de07eaaa48bd1db4a89a7986771"
JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
GENERATOR="Ninja"
BUILD_TYPE="Release"

usage() {
  cat <<'USAGE'
Usage: scripts/bootstrap_n64recomp.sh [options]

Options:
  --prefix PATH       Clone/build location. Default: $PWD/.deps/N64Recomp
  --ref REF           Git ref, branch, tag, or commit. Default: pinned release commit
  --jobs N            Parallel build jobs. Default: detected CPU count
  --generator NAME    CMake generator. Default: Ninja
  --debug             Build Debug instead of Release
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --generator) GENERATOR="$2"; shift 2 ;;
    --debug) BUILD_TYPE="Debug"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}
need git
need cmake
if [[ "$GENERATOR" == "Ninja" ]]; then need ninja; fi

mkdir -p "$(dirname "$PREFIX")"
if [[ ! -d "$PREFIX/.git" ]]; then
  git clone --recurse-submodules https://github.com/N64Recomp/N64Recomp.git "$PREFIX"
fi
cd "$PREFIX"
git fetch --tags --prune
git checkout --detach "$REF"
if [[ "$REF" =~ ^[0-9a-fA-F]{40}$ ]] && [[ "$(git rev-parse HEAD)" != "${REF,,}" ]]; then
  echo "N64Recomp checkout did not resolve to $REF" >&2
  exit 1
fi
git submodule update --init --recursive

cmake -S . -B build -G "$GENERATOR" -DCMAKE_BUILD_TYPE="$BUILD_TYPE"
cmake --build build --parallel "$JOBS"

echo "Built N64Recomp at: $PREFIX/build/N64Recomp"
if [[ -x "$PREFIX/build/RSPRecomp" ]]; then echo "Built RSPRecomp at: $PREFIX/build/RSPRecomp"; fi
if [[ -x "$PREFIX/build/RecompModTool" ]]; then echo "Built RecompModTool at: $PREFIX/build/RecompModTool"; fi
