#!/usr/bin/env python3
"""Baseline static repository policy checks for Decypher legacy repos."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
ERRORS: list[str] = []
WARNINGS: list[str] = []
GENERATED_DIRS = {"node_modules", ".venv", "venv", ".pytest_cache", "__pycache__", ".angular", ".cache", "coverage", "dist", "build"}
SECRET_PATTERNS = ("BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN=")


def tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(["git", "ls-files"], text=True)
        return [Path(line) for line in out.splitlines() if line]
    except Exception:
        return []


def main() -> int:
    files = tracked_files()
    if not any((ROOT / n).exists() for n in ("README.md", "readme.md", "README.txt")):
        WARNINGS.append("README is missing; add purpose/setup/test/deploy notes")
    for dirname in GENERATED_DIRS:
        if any(p.parts and p.parts[0] == dirname for p in files):
            WARNINGS.append(f"Generated/cache path is committed and should be reviewed: {dirname}/")
    for rel in files:
        if rel.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".dll", ".exe"}:
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:200000]
        except Exception:
            continue
        for marker in SECRET_PATTERNS:
            if marker in text:
                ERRORS.append(f"Possible committed secret marker {marker!r} in {rel.as_posix()}")
    for warning in WARNINGS:
        print(f"::warning::{warning}")
    if ERRORS:
        print("Repository policy check failed:")
        for error in ERRORS:
            print(f"::error::{error}")
        return 1
    print("Repository policy checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
