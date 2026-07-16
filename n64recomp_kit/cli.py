from __future__ import annotations

from .commands.dispatch import dispatch
from .commands.parser import build_parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
