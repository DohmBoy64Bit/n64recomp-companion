#!/usr/bin/env python3
"""Batch-check or batch-run configs."""
from n64recomp_kit.cli import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(["batch"] + sys.argv[1:]))
