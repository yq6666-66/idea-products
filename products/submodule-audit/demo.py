#!/usr/bin/env python3
"""Simple demo for submodule-audit: builds its own temp root with
three repositories (one healthy, one uninitialized, one with a
commit mismatch), runs the audit, prints the table, then cleans
up its temp directory.

Usage:
    python3 demo.py

It touches nothing outside its own temp directory, never runs
git submodule init or update, and never writes to the scanned
repositories.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "submodule-audit.py"


def git(directory, *args, allow_file=False):
    cmd = ["git", "-C", str(directory)]
    if allow_file:
        cmd += ["-c", "protocol.file.allow=always"]
    cmd += list(args)
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   timeout=60)


def init_repo(directory, files=None):
    directory.mkdir(parents=True, exist_ok=True)
    git(directory, "init", "-q", "-b", "main")
    git(directory, "config", "user.email", "demo@example.com")
    git(directory, "config", "user.name", "Demo")
    for name, text in (files or {}).items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(directory, "add", "-A")
    git(directory, "commit", "-qm", "init")
    return directory


def add_sub(parent, origin, name):
    git(parent, "submodule", "add", "-q", str(origin), name,
        allow_file=True)
    git(parent, "commit", "-qm", f"add {name}")


def main():
    with tempfile.TemporaryDirectory(
            prefix="submodule-audit-demo-") as tmp:
        base = Path(tmp)
        origin = init_repo(base / "origin-sub", {"f.txt": "sub\n"})
        root = base / "root"
        root.mkdir()
        healthy = init_repo(root / "healthy", {"a.txt": "a\n"})
        add_sub(healthy, origin, "sub1")
        uninit = init_repo(root / "uninit", {"a.txt": "a\n"})
        add_sub(uninit, origin, "sub1")
        git(uninit, "submodule", "deinit", "-q", "-f", "sub1")
        mismatch = init_repo(root / "mismatch", {"a.txt": "a\n"})
        add_sub(mismatch, origin, "sub1")
        git(mismatch / "sub1", "config", "user.email",
            "demo@example.com")
        git(mismatch / "sub1", "config", "user.name", "Demo")
        (mismatch / "sub1" / "f.txt").write_text("sub changed\n")
        git(mismatch / "sub1", "add", "-A")
        git(mismatch / "sub1", "commit", "-qm", "local change")
        print("=== submodule-audit on a temp demo root ===")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(root)],
            capture_output=True, text=True, timeout=180)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    print("\nDemo temp dir cleaned up. Nothing was changed.")


if __name__ == "__main__":
    main()
