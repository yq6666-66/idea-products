#!/usr/bin/env python3
"""Read-only bidirectional .gitignore audit for one git repository.

Prints two lists and nothing else is changed:
  A. tracked files that match an ignore rule (they were committed
     before the rule existed, because once a file is tracked,
     .gitignore no longer applies to it);
  B. untracked, unignored files that resemble build products or
     local files, labelled "suspected", never a verdict.

All matching is done by git itself (git ls-files, git check-ignore);
this script never re-implements .gitignore matching and never
guesses a rule's priority.

Usage:
    python3 gitignore-audit.py <repo-dir> [--json]

Red lines: never runs git add, git rm or git clean, never writes
.gitignore, never deletes a file, never installs anything. Only
file paths are listed, never file contents.

Known limits:
  - The product-appearance table is a heuristic and can misreport
    (some projects intentionally commit dist/); list B is "suspected".
  - File contents are not judged; a path that looks like a secret
    is only listed, the risk is for the user to judge.
  - git must be installed and the directory must be a git repository;
    otherwise this exits 2 and says so, instead of parsing
    .gitignore itself.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Directory names that look like build or local products.
PRODUCT_DIRS = {
    "node_modules", "__pycache__", "dist", "build", "target",
    ".venv", "venv", ".egg-info", ".cache",
}
# File suffixes that look like build products or local files.
PRODUCT_SUFFIXES = {
    ".pyc", ".pyo", ".log", ".tmp", ".DS_Store", ".env", ".swp",
}

CHECK_IGNORE = re.compile(r"^(.+):(\d+):(.*)\t(.*)$")


def run_git(directory, *args):
    import subprocess
    result = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True, text=True, timeout=60)
    return result


def is_git_repo(directory):
    result = run_git(directory, "rev-parse", "--git-dir")
    return result.returncode == 0


def check_ignore(directory, path):
    """Return (source_file, line, rule) for one path, or None.

    --no-index is required: without it git check-ignore reports
    nothing for tracked files, which is exactly what list A is
    made of. A pattern starting with '!' is a negation, meaning
    the file is NOT ignored, so it returns None.
    """
    result = run_git(directory, "check-ignore", "-v", "--no-index",
                     "--", path)
    if result.returncode != 0:
        return None
    line = result.stdout.strip().splitlines()
    if not line:
        return None
    match = CHECK_IGNORE.match(line[0])
    if not match:
        return None
    if match.group(3).startswith("!"):
        return None
    return match.group(1), int(match.group(2)), match.group(3)


def suspected_type(path):
    """Return a suspected-type label for a path, or None."""
    parts = Path(path).parts
    for part in parts:
        if part in PRODUCT_DIRS:
            return f"build/local directory: {part}"
        if part.endswith(".egg-info"):
            return "build directory: .egg-info"
    name = parts[-1] if parts else ""
    for suffix in sorted(PRODUCT_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            if suffix == ".env":
                return "local config: .env"
            if suffix in (".log", ".tmp", ".DS_Store", ".swp"):
                return f"local file: {suffix}"
            return f"build artifact: {suffix}"
    return None


def collect(directory):
    """Return (list_a, list_b, skipped, notes)."""
    skipped, notes = [], []
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        notes.append("no .gitignore in this repo: list A is empty")
    result = run_git(directory, "ls-files", "--cached", "--ignored",
                     "--exclude-standard")
    list_a = []
    for path in result.stdout.splitlines():
        path = path.strip()
        if not path:
            continue
        info = check_ignore(directory, path)
        if info is None:
            skipped.append((path, "check-ignore gave no rule"))
            rule, source, line = "unknown", "unknown", 0
        else:
            source, line, rule = info
        list_a.append({
            "path": path,
            "rule": rule,
            "source_file": source,
            "source_line": line,
            "suggestion": f"git rm --cached {path}",
        })
    result = run_git(directory, "ls-files", "--others", "--exclude-standard")
    list_b = []
    for path in result.stdout.splitlines():
        path = path.strip()
        if not path or path.startswith(".git/"):
            continue
        kind = suspected_type(path)
        if kind is None:
            continue
        list_b.append({
            "path": path,
            "suspected_type": kind,
            "suggestion": "add to .gitignore or remove",
        })
    return list_a, list_b, skipped, notes


def print_table(list_a, list_b):
    print("List A: tracked files matching an ignore rule")
    if not list_a:
        print("  (none)")
    else:
        headers = ("PATH", "RULE", "SOURCE", "SUGGESTION")
        rows = [headers] + [(a["path"], a["rule"],
                             f"{a['source_file']}:{a['source_line']}",
                             a["suggestion"]) for a in list_a]
        widths = [max(len(r[i]) for r in rows) for i in range(4)]
        for row in rows:
            print("  ".join(cell.ljust(widths[i])
                            for i, cell in enumerate(row)))
    print("\nList B: untracked files resembling build/local products "
          "(suspected)")
    if not list_b:
        print("  (none)")
    else:
        headers = ("PATH", "SUSPECTED TYPE", "SUGGESTION")
        rows = [headers] + [(b["path"], b["suspected_type"],
                             b["suggestion"]) for b in list_b]
        widths = [max(len(r[i]) for r in rows) for i in range(3)]
        for row in rows:
            print("  ".join(cell.ljust(widths[i])
                            for i, cell in enumerate(row)))


def print_summary(list_a, list_b, skipped, notes, stream):
    print(f"tracked_ignored: {len(list_a)}, "
          f"untracked_suspected: {len(list_b)}, "
          f"skipped: {len(skipped)}", file=stream)
    for name, reason in skipped:
        print(f"  skipped {name}: {reason}", file=stream)
    for note in notes:
        print(f"  note {note}", file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Bidirectional .gitignore audit, read-only.")
    parser.add_argument("directory", help="git repository to scan")
    parser.add_argument("--json", action="store_true",
                        help="output two JSON arrays")
    args = parser.parse_args(argv)
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    try:
        repo = is_git_repo(directory)
    except FileNotFoundError:
        print("error: git is not installed", file=sys.stderr)
        return 2
    if not repo:
        print(f"error: not a git repository: {directory}",
              file=sys.stderr)
        return 2
    list_a, list_b, skipped, notes = collect(directory)
    if args.json:
        print(json.dumps({"tracked_ignored": list_a,
                          "untracked_suspected": list_b},
                         ensure_ascii=False, indent=2))
        print_summary(list_a, list_b, skipped, notes, sys.stderr)
    else:
        print_table(list_a, list_b)
        print_summary(list_a, list_b, skipped, notes, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
