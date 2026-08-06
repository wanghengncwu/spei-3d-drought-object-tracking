#!/usr/bin/env python3
"""Run repository checks and verify Python build artifacts."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
IGNORED_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "data",
    "dist",
    "outputs",
    "results",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify repository checks and Python build artifacts."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="run lint, tests, and audit without building distributions",
    )
    return parser


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    printable = " ".join(command)
    print(f"\n$ {printable}")
    subprocess.run(command, cwd=cwd, env=env, check=True)


def copy_release_tree(source: Path, destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in IGNORED_NAMES}
        ignored.update(name for name in names if name.endswith(".egg-info"))
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        return ignored

    shutil.copytree(source, destination, ignore=ignore)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    run([sys.executable, "-m", "ruff", "check", "."], cwd=REPOSITORY_ROOT, env=environment)
    run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"],
        cwd=REPOSITORY_ROOT,
        env=environment,
    )

    with tempfile.TemporaryDirectory(prefix="spei3d-release-") as temporary:
        temporary_root = Path(temporary)
        release_tree = temporary_root / "spei-3d-drought-object-tracking"
        copy_release_tree(REPOSITORY_ROOT, release_tree)
        run(
            [sys.executable, "scripts/audit_release.py", "."],
            cwd=release_tree,
            env=environment,
        )
        if not args.skip_build:
            distribution_dir = temporary_root / "dist"
            run(
                [sys.executable, "-m", "build", "--outdir", str(distribution_dir)],
                cwd=release_tree,
                env=environment,
            )
            artifacts = sorted(path.name for path in distribution_dir.iterdir())
            if len(artifacts) != 2 or not any(name.endswith(".whl") for name in artifacts):
                raise RuntimeError(f"unexpected build artifacts: {artifacts}")
            if not any(name.endswith(".tar.gz") for name in artifacts):
                raise RuntimeError(f"source distribution is missing: {artifacts}")
            print("\nBuild artifacts:")
            for artifact in artifacts:
                print(f"- {artifact}")

    print("\nRelease verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
