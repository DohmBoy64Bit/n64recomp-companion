#!/usr/bin/env bash
set -euo pipefail
IMAGE="n64recomp-companion:latest"
N64RECOMP_REF="ffb39cdad1da5de07eaaa48bd1db4a89a7986771"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --ref) N64RECOMP_REF="$2"; shift 2 ;;
    -h|--help) echo "Usage: scripts/build_podman_image.sh [--image NAME] [--ref GIT_REF]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
podman build --build-arg N64RECOMP_REF="$N64RECOMP_REF" -t "$IMAGE" -f Containerfile .
