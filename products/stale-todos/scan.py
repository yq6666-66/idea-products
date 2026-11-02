#!/usr/bin/env python3
"""List TODO/FIXME in comments with git-blame age, oldest first. Read-only."""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MARKER_RE = re.compile(r"\b(TODO|FIXME)\b")
# rough comment prefixes / inline comment starters by language family
LINE_COMMENT = re.compile(
    r"""(?x)
    ^\s*(?:
        //+|          # C/JS/Go/Rust/...
        \#(?!!)|      # shell/python (not shebang #!)
        --+|          # SQL/Lua/Haskell
        ;+|           # Lisp/asm-ish
        \*+           # continuation inside block comment
    )
    """
)
INLINE_COMMENT = re.compile(r"(?://+|\#(?!!)|--+|;+)\s*.*\b(TODO|FIXME)\b")
STRING_ONLY_LINE = re.compile(
    r"""(?x)
    ^\s*(?:
        (?:r|u|f|b|fr|rf)?['\"].*['\"]|
        `.*`|
        ["'].*["']
    )\s*,?\s*$
    """
)
TEST_PATH_HINTS = (
    "/test/",
    "/tests/",
    "/__tests__/",
    "/fixtures/",
    "/testdata/",
    "/samples/",
    "_test.",
    ".test.",
    ".spec.",
)
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


def is_testish(rel: Path) -> bool:
    s = "/" + str(rel).replace("\\", "/").lower()
    name = rel.name.lower()
    if any(h in s for h in TEST_PATH_HINTS):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


def in_comment(line: str) -> bool:
    if LINE_COMMENT.search(line):
        return True
    if INLINE_COMMENT.search(line):
        return True
    # block comment open on same line: /* ... TODO
    if "/*" in line and MARKER_RE.search(line.split("/*", 1)[1]):
        return True
    return False


def looks_like_string_literal_hit(line: str) -> bool:
    """Skip obvious assertion / fixture string lines that aren't comments."""
    if in_comment(line):
        return False
    stripped = line.strip()
    if STRING_ONLY_LINE.match(stripped):
        return True
    # e.g. assert "TODO" in x / expect('FIXME')
    if re.search(r"""['\"`].*\b(TODO|FIXME)\b.*['\"`]""", line) and not in_comment(line):
        return True
    return False


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
    ap.add_argument(
        "--include-tests",
        action="store_true",
        help="also scan test/fixture paths (still skips non-comment string literals)",
    )
    args = ap.parse_args()
    repo = args.repo.resolve()
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"not a git work tree: {repo}")

    rows = []
    for path in iter_files(repo):
        rel = path.relative_to(repo)
        if not args.include_tests and is_testish(rel):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            m = MARKER_RE.search(line)
            if not m:
                continue
            if looks_like_string_literal_hit(line):
                continue
            if not in_comment(line):
                continue
            when = blame_date(repo, path, i) or "0000-00-00"
            text = line.strip()
            if len(text) > 120:
                text = text[:117] + "..."
            rows.append((when, m.group(1), rel, i, text))

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
