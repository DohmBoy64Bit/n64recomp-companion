#!/usr/bin/env python3
"""Inspect an N64 ROM header."""
from n64recomp_kit.cli import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(["rom-info"] + sys.argv[1:]))
