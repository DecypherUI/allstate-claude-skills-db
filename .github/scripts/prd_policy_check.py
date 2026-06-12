#!/usr/bin/env python3
"""Enforce Decypher PRD placement/date rules with readable messages.

Rules:
- Active PRDs: documents/prds/YYYY-MM-DD-short-title.md
- Completed PRDs: documents/prds/archive/YYYY-MM-DD-short-title.md

Legacy invalid PRDs already on the target branch are reported as warnings. New or changed
invalid PRDs in a PR are errors. This keeps rollout from turning old repositories red while
still preventing new PRD drift.
"""
from __future__ import annotations
import os
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

def changed_files() -> set[str]:
    base = os.environ.get("GITHUB_BASE_REF")
    if not base:
        return set()
    try:
        subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", base], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = git("diff", "--name-only", f"origin/{base}...HEAD")
        return {x for x in out.splitlines() if x}
    except Exception:
        return set()

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

def violations(rel: Path) -> list[str]:
    s = rel.as_posix()
    out=[]
    if not s.startswith(ALLOWED_PREFIXES):
        out.append(
            f"{s}: PRD is in the wrong folder. Active PRDs belong in documents/prds/; completed PRDs belong in documents/prds/archive/."
        )
        return out
    if not DATE_RE.match(rel.name):
        out.append(f"{s}: PRD filename must start with YYYY-MM-DD-, for example documents/prds/2026-06-12-feature-name.md.")
    if s.startswith("documents/prds/") and not s.startswith("documents/prds/archive/") and rel.parent.as_posix() != "documents/prds":
        out.append(f"{s}: active PRDs must be directly under documents/prds/. Use documents/prds/archive/ only for completed PRDs.")
    return out

def main() -> int:
    changed = changed_files()
    prds = [p for p in tracked_files() if looks_like_prd(p)]
    for rel in prds:
        for msg in violations(rel):
            if rel.as_posix() in changed:
                ERRORS.append(msg + " Move/rename this PRD before merging this PR.")
            else:
                WARNINGS.append("Legacy PRD convention issue: " + msg)
    if not (ROOT / "documents" / "prds").exists():
        WARNINGS.append("documents/prds/ does not exist yet; create it when adding active PRDs.")
    for warning in WARNINGS:
        print(f"::warning::{warning}")
    if ERRORS:
        print("PRD policy check failed. New or changed PRDs must follow Decypher's PRD location/name convention:")
        for error in ERRORS:
            print(f"::error::{error}")
        return 1
    print(f"PRD policy checks passed ({len(prds)} PRD-like markdown file(s) checked; legacy issues are warnings only)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
