#!/usr/bin/env python3
"""Run N64Recomp with validation."""
from n64recomp_kit.cli import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(["run"] + sys.argv[1:]))
