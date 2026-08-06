#!/usr/bin/env python3
"""Audit a repository tree for hygiene issues and machine-specific traces."""

from __future__ import annotations

import re
import sys
from pathlib import Path

CACHE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
GENERATED_DIRS = {"build", "dist"}
OUTPUT_DIRS = {"data", "outputs", "results"}
RESEARCH_DATA_SUFFIXES = {
    ".nc",
    ".nc4",
    ".npy",
    ".npz",
    ".parquet",
    ".h5",
    ".hdf5",
    ".grib",
    ".grb",
    ".zarr",
}
BINARY_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".zip",
    ".pdf",
    ".docx",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".cff",
    ".csv",
}
SECRET_RULES = [
    ("credential-like secret", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("credential-like secret", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("credential-like secret", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("credential-like secret", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]
CONTENT_RULES = [
    ("absolute Windows path", re.compile(r"[A-Za-z]:\\(?:[^\\\r\n]+\\)+")),
    ("personal absolute Unix path", re.compile(r"/(?:home|Users|mnt/data)/")),
    ("manuscript identifier", re.compile(r"\bHYDROL\d+\b", re.IGNORECASE)),
    ("email address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("local username marker", re.compile(r"\b(?:00wangheng|wangheng)\b", re.IGNORECASE)),
]


def audit_repository(root: Path) -> list[str]:
    root = root.resolve()
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if ".git" in parts:
            continue
        if any(part in CACHE_DIRS for part in relative.parts):
            if path.is_dir():
                findings.append(f"cache directory: {relative}")
            continue
        if any(
            part in GENERATED_DIRS or part.endswith(".egg-info")
            for part in relative.parts
        ):
            if path.is_dir():
                findings.append(f"generated build directory: {relative}")
            continue
        if any(part in OUTPUT_DIRS for part in relative.parts):
            if path.is_dir():
                findings.append(f"generated output directory: {relative}")
            continue
        if path.is_dir():
            if path.suffix.lower() == ".zarr":
                findings.append(f"data artifact: {relative}")
            continue
        if path.name == ".env" or path.suffix.lower() in {".pem", ".key"}:
            findings.append(f"environment file: {relative}")
        if path.suffix.lower() in RESEARCH_DATA_SUFFIXES:
            findings.append(f"data artifact: {relative}")
        if path.suffix.lower() in BINARY_SUFFIXES:
            findings.append(f"binary or non-code artifact: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if relative.parts and relative.parts[0] == "tests":
            continue
        if relative.as_posix() == "scripts/audit_release.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF-8 text file: {relative}")
            continue
        for label, pattern in [*CONTENT_RULES, *SECRET_RULES]:
            if pattern.search(text):
                findings.append(f"{label}: {relative}")
    return sorted(set(findings))


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    root = Path(arguments[0]) if arguments else Path.cwd()
    findings = audit_repository(root)
    if findings:
        print("Release audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"Release audit passed: {root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
