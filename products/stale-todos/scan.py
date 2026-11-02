#!/usr/bin/env python3
"""List TODO/FIXME with git-blame age, oldest first. Read-only."""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MARKER_RE = re.compile(r"\b(TODO|FIXME)\b")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".pytest_cache"}
TEXT_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".m", ".mm", ".sh", ".bash", ".zsh", ".md", ".txt", ".yml",
    ".yaml", ".toml", ".json", ".css", ".scss", ".html", ".vue", ".svelte",
}


def iter_files(repo: Path):
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in TEXT_EXT and p.name not in {"Makefile", "Dockerfile"}:
            continue
        yield p


def blame_date(repo: Path, path: Path, line_no: int) -> str | None:
    r = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "blame",
            "-L",
            f"{line_no},{line_no}",
            "--line-porcelain",
            "--",
            str(path.relative_to(repo)),
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if line.startswith("author-time "):
            ts = int(line.split()[1])
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", type=Path)
    args = ap.parse_args()
    repo = args.repo.resolve()
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"not a git work tree: {repo}")

    rows = []
    for path in iter_files(repo):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            m = MARKER_RE.search(line)
            if not m:
                continue
            when = blame_date(repo, path, i) or "0000-00-00"
            text = line.strip()
            if len(text) > 120:
                text = text[:117] + "..."
            rows.append((when, m.group(1), path.relative_to(repo), i, text))

    rows.sort(key=lambda x: x[0])
    print("# stale-todos")
    print(f"repo: {repo}")
    print(f"count: {len(rows)}")
    print(f"generated_at: {datetime.now(timezone.utc).isoformat()}")
    print()
    if not rows:
        print("(none)")
        return
    print("AGE_DATE  TAG    LOCATION  TEXT")
    today = datetime.now(timezone.utc).date()
    for when, tag, rel, lineno, text in rows:
        try:
            age_days = (today - datetime.fromisoformat(when).date()).days
            age = f"{age_days}d"
        except ValueError:
            age = "?"
        print(f"{when}  {age:>5}  {tag:5}  {rel}:{lineno}  {text}")


if __name__ == "__main__":
    main()
