#!/usr/bin/env python3
"""Command line entry point for the internal capture-golden package."""
from __future__ import annotations

import argparse
import sys

from . import batch, cics


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="capture-golden")
    sub = parser.add_subparsers(dest="command", required=True)

    cics_parser = sub.add_parser("cics", help="capture CICS 3270 screens")
    cics.add_arguments(cics_parser)

    batch_parser = sub.add_parser("batch", help="run batch jobs and export datasets")
    batch.add_arguments(batch_parser)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "cics":
        return cics.run_from_args(args)
    if args.command == "batch":
        return batch.run_from_args(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
