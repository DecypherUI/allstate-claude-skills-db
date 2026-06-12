#!/usr/bin/env python3
"""Enforce Decypher PRD placement and date-stamped filenames.

Active PRDs must live in documents/prds/.
Completed PRDs must live in documents/prds/archive/.
PRD filenames must start with YYYY-MM-DD-.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[-_].+\.md$", re.IGNORECASE)
PRD_NAME_RE = re.compile(r"prd|product[-_ ]requirements", re.IGNORECASE)
PRD_HEADING_RE = re.compile(r"^#\s*(prd|product\s+requirements)", re.IGNORECASE | re.MULTILINE)
ALLOWED_PREFIXES = ("documents/prds/", "documents/prds/archive/")
ERRORS: list[str] = []
WARNINGS: list[str] = []


def tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(["git", "ls-files"], text=True)
        return [Path(line) for line in out.splitlines() if line]
    except Exception:
        return [p.relative_to(ROOT) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def looks_like_prd(rel: Path) -> bool:
    s = rel.as_posix()
    if rel.suffix.lower() not in {".md", ".markdown"}:
        return False
    if PRD_NAME_RE.search(s):
        return True
    try:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")[:12000]
    except Exception:
        return False
    return bool(PRD_HEADING_RE.search(text))


def check_prd(rel: Path) -> None:
    s = rel.as_posix()
    if not s.startswith(ALLOWED_PREFIXES):
        ERRORS.append(
            f"PRD must be under documents/prds/ or documents/prds/archive/: {s}"
        )
        return
    name = rel.name
    if not DATE_RE.match(name):
        ERRORS.append(
            f"PRD filename must start with YYYY-MM-DD-: {s}"
        )
    if s.startswith("documents/prds/archive/"):
        return
    # Active PRDs must be directly under documents/prds/, not nested elsewhere.
    parent = rel.parent.as_posix()
    if parent != "documents/prds":
        ERRORS.append(
            f"Active PRD must be directly under documents/prds/; completed PRDs go under documents/prds/archive/: {s}"
        )


def main() -> int:
    prds = [p for p in tracked_files() if looks_like_prd(p)]
    for rel in prds:
        check_prd(rel)
    if not (ROOT / "documents" / "prds").exists():
        WARNINGS.append("documents/prds/ does not exist yet; create it when adding active PRDs")
    for warning in WARNINGS:
        print(f"::warning::{warning}")
    if ERRORS:
        print("PRD policy check failed:")
        for error in ERRORS:
            print(f"::error::{error}")
        return 1
    print(f"PRD policy checks passed ({len(prds)} PRD-like markdown file(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
