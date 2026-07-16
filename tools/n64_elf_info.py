#!/usr/bin/env python3
"""Inspect an ELF32 file."""
from n64recomp_kit.cli import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(["elf-info"] + sys.argv[1:]))
