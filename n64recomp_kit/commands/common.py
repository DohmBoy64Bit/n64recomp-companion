from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import TypeAlias

CommandHandler: TypeAlias = Callable[[argparse.Namespace], int | None]


def add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
