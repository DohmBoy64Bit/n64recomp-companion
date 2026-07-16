#!/usr/bin/env python3
from n64recomp_kit.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["workspace-status"] + __import__("sys").argv[1:]))
