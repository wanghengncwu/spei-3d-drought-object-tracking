"""Command-line interface for the drought-object workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .config import load_config
from .engine import run_extraction
from .sensitivity import run_sensitivity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spei3d",
        description="Extract 3-D drought objects from precomputed SPEI fields.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="run one drought-object extraction")
    extract.add_argument("--config", required=True, type=Path)

    sensitivity = subparsers.add_parser(
        "sensitivity", help="run one-factor-at-a-time sensitivity experiments"
    )
    sensitivity.add_argument("--config", required=True, type=Path)

    validate = subparsers.add_parser(
        "validate-config", help="validate YAML structure and parameter values"
    )
    validate.add_argument("--config", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "validate-config":
        print(f"Configuration is valid: {args.config}")
        return 0
    if args.command == "extract":
        summary = run_extraction(config)
        print(f"Retained objects: {summary.object_count}")
        print(f"Output directory: {summary.output_dir}")
        return 0
    if args.command == "sensitivity":
        path = run_sensitivity(config)
        print(f"Sensitivity summary: {path}")
        return 0
    raise RuntimeError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
