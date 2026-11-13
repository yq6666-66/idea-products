#!/usr/bin/env python3
"""Read-only scan for hardcoded absolute paths in a repository.

Walks one directory, reads only code and config files by extension
whitelist, and lists every absolute path found (Windows drive letter,
UNC, or POSIX), grouped by file with line numbers. It never writes,
deletes, or installs anything, and it never prints a whole line of
source, only the matched path, its file and its line number.

Usage:
    python3 hardcoded-path-scan.py <repo-dir> [--json]

Red lines: read-only, no file writes or deletes, no dependency
installs; only the one directory given is scanned; a matched path
is reported as-is, never judged on whether it is really used at
runtime, so every hit is labelled suspected and needs a human look.

Known limits:
  - Regular expressions only see the text shape; a path in dead
    code is reported too, and a path built by joining pieces
    (for example os.path.join(os.environ["HOME"], "data")) is
    not found at all, which is correct behaviour for that case.
  - A string split across lines or with escaped backslashes can
    be missed; this version does single-line regex only, no
    syntax parsing.
  - Large repositories are scanned once with no cache, so a big
    tree may be slow.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Only code and config files are scanned; anything else is skipped
# and counted in the summary.
SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".sh", ".bat", ".ps1",
}
# Directories never entered.
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
    "build",
}
# POSIX top-level directories that count as a hardcoded absolute
# path; a bare "/" on its own is not one.
POSIX_TOP_DIRS = (
    "home", "Users", "etc", "var", "opt", "root", "tmp", "usr",
    "srv", "mnt", "media", "data", "workspace",
)

DRIVE_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>\)\]]+")
UNC_RE = re.compile(r"\\\\[A-Za-z0-9._-]+\\[^\s\"'<>]+")
POSIX_RE = re.compile(
    r"/(?:%s)(?:/[^\s\"'<>\\]+)*" % "|".join(POSIX_TOP_DIRS))
URL_RE = re.compile(r"https?://\S+")

SUGGESTION = "疑似：改成相对路径、环境变量或配置项"

TRAILING_PUNCT = ",;)]}'\""


def clean_path(path):
    """Trim punctuation that belongs to the surrounding text."""
    return path.rstrip(TRAILING_PUNCT).rstrip("\\")


def find_paths(line):
    """Return [(path, kind)] for one line, in order, no overlaps."""
    if line.lstrip().startswith("#!"):
        return []
    line = URL_RE.sub("", line)
    hits, spans = [], []

    def add(match, kind):
        path = clean_path(match.group(0))
        if not path:
            return
        start, end = match.span()
        if any(start < e and s < end for s, e in spans):
            return
        spans.append((start, end))
        hits.append((path, kind))

    for match in DRIVE_RE.finditer(line):
        add(match, "盘符")
    for match in UNC_RE.finditer(line):
        add(match, "UNC")
    for match in POSIX_RE.finditer(line):
        add(match, "POSIX")
    return hits


def is_binary(path):
    with open(path, "rb") as handle:
        return b"\x00" in handle.read(8192)


def collect(directory):
    """Return (hits, scanned, skipped) for one directory."""
    hits = []
    scanned = 0
    skipped = {"extension": 0, "binary": 0, "directory": 0}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(directory).parts[:-1]):
            skipped["directory"] += 1
            continue
        if path.suffix not in SCAN_EXTENSIONS:
            skipped["extension"] += 1
            continue
        if is_binary(path):
            skipped["binary"] += 1
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            for found, kind in find_paths(line):
                hits.append({
                    "file": str(path.relative_to(directory)),
                    "line": number,
                    "path": found,
                    "kind": kind,
                    "suggestion": SUGGESTION,
                })
    return hits, scanned, skipped


def print_table(hits):
    if not hits:
        print("  (none)")
        return
    grouped = {}
    for hit in hits:
        grouped.setdefault(hit["file"], []).append(hit)
    headers = ("LINE", "PATH", "KIND", "SUGGESTION")
    for filename, rows in grouped.items():
        print(f"\n{filename}")
        table = [headers] + [(str(r["line"]), r["path"], r["kind"],
                              r["suggestion"]) for r in rows]
        widths = [max(len(r[i]) for r in table) for i in range(4)]
        for row in table:
            print("  " + "  ".join(cell.ljust(widths[i])
                                   for i, cell in enumerate(row)))


def print_summary(hits, scanned, skipped, stream):
    total = sum(skipped.values())
    print(f"scanned: {scanned} file(s), hits: {len(hits)}, "
          f"skipped: {total} file(s) "
          f"(extension: {skipped['extension']}, "
          f"binary: {skipped['binary']}, "
          f"directory: {skipped['directory']})", file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Hardcoded absolute path scan, read-only.")
    parser.add_argument("directory", help="directory to scan")
    parser.add_argument("--json", action="store_true",
                        help="output hits as a JSON array")
    args = parser.parse_args(argv)
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    hits, scanned, skipped = collect(directory)
    if args.json:
        print(json.dumps(
            [{k: h[k] for k in ("file", "line", "path", "kind")}
             for h in hits], ensure_ascii=False, indent=2))
        print_summary(hits, scanned, skipped, sys.stderr)
    else:
        print_table(hits)
        print_summary(hits, scanned, skipped, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
