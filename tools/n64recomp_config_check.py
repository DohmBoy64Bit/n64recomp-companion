#!/usr/bin/env python3
"""Validate an N64Recomp TOML config."""
from n64recomp_kit.cli import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(["check-config"] + sys.argv[1:]))
