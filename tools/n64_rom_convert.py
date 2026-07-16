#!/usr/bin/env python3
"""Convert N64 ROM byte order to z64."""
from n64recomp_kit.cli import main
import sys

if __name__ == "__main__":
    raise SystemExit(main(["convert-rom"] + sys.argv[1:]))
