#!/usr/bin/env bash
set -euo pipefail
WORKDIR="${1:-$PWD}"
IMAGE="${N64RECOMP_IMAGE:-n64recomp-companion:latest}"
podman run --rm -it \
  -v "$(cd "$WORKDIR" && pwd):/work:Z" \
  -w /work \
  "$IMAGE" \
  bash
