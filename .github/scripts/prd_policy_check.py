#!/usr/bin/env python3
"""Enforce Decypher PRD/documentation placement and date-stamped filenames.

Rules:
- Active PRDs: documents/prds/YYYY-MM-DD-short-title.md
- Completed PRDs: documents/prds/archive/YYYY-MM-DD-short-title.md

This is intentionally a hard CI gate. Existing legacy violations fail too: the goal is to
make incorrect documentation placement visible before branch protection makes the check
unmergeable.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path.cwd()
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[-_].+\.(md|markdown)$", re.I)
PRD_NAME_RE = re.compile(r"prd|product[-_ ]requirements", re.I)
PRD_HEADING_RE = re.compile(r"^#\s*(prd|product\s+requirements)", re.I | re.M)
ALLOWED_PREFIXES = ("documents/prds/", "documents/prds/archive/")
ERRORS: list[str] = []
WARNINGS: list[str] = []
def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL)
def tracked_files() -> list[Path]:
    return [Path(x) for x in git("ls-files").splitlines() if x]
def looks_like_prd(rel: Path) -> bool:
    s = rel.as_posix()
    if rel.suffix.lower() not in {".md", ".markdown"}: return False
    if PRD_NAME_RE.search(s): return True
    try: text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")[:12000]
    except Exception: return False
    return bool(PRD_HEADING_RE.search(text))
def validate_prd(rel: Path) -> None:
    s = rel.as_posix()
    if not s.startswith(ALLOWED_PREFIXES):
        ERRORS.append(f"{s}: PRD is in the wrong folder. Active PRDs must be in documents/prds/; completed PRDs must be in documents/prds/archive/. Move this file and date-stamp the filename.")
        return
    if not DATE_RE.match(rel.name):
        ERRORS.append(f"{s}: PRD filename must start with YYYY-MM-DD-, for example documents/prds/2026-06-12-feature-name.md.")
    if s.startswith("documents/prds/") and not s.startswith("documents/prds/archive/") and rel.parent.as_posix() != "documents/prds":
        ERRORS.append(f"{s}: active PRDs must be directly under documents/prds/. Use documents/prds/archive/ only for completed PRDs.")
def main() -> int:
    prds = [p for p in tracked_files() if looks_like_prd(p)]
    for rel in prds: validate_prd(rel)
    if not (ROOT / "documents" / "prds").exists():
        ERRORS.append("documents/prds/ is required. Projects must be fully documented with active PRDs in documents/prds/ and completed PRDs in documents/prds/archive/.")
    for warning in WARNINGS: print(f"::warning::{warning}")
    if ERRORS:
        print("PRD/documentation policy check failed. Decypher documentation must live in the standard project folders so reviewers and agents can find it:")
        print("  Active PRDs:    documents/prds/YYYY-MM-DD-short-title.md")
        print("  Completed PRDs: documents/prds/archive/YYYY-MM-DD-short-title.md")
        for error in ERRORS: print(f"::error::{error}")
        return 1
    print(f"PRD/documentation policy checks passed ({len(prds)} PRD-like markdown file(s) checked)")
    return 0
if __name__ == "__main__": sys.exit(main())
