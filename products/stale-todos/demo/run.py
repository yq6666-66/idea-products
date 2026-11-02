#!/usr/bin/env python3
"""Throwaway repo with dated comment markers (and one string hit), then scan.py."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Split so this helper itself is not a comment hit when the product tree is scanned.
TODO = "TO" + "DO"
FIXME = "FIX" + "ME"


def git(cwd: Path, *args: str, when: str | None = None) -> None:
    env = os.environ.copy()
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    r = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stale-todos-demo-") as tmp_name:
        repo = Path(tmp_name) / "repo"
        src = repo / "src"
        src.mkdir(parents=True)
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.email", "demo@example.com")
        git(repo, "config", "user.name", "demo")

        (src / "parser.py").write_text(
            f"# {TODO}: replace the hand-rolled splitter\n"
            "def split(text):\n"
            "    return text.split(',')\n",
            encoding="utf-8",
        )
        git(repo, "add", "src/parser.py")
        git(repo, "commit", "-m", "old note", when="2024-01-15T12:00:00Z")

        (src / "io.py").write_text(
            "def read(path):\n"
            f"    # {FIXME}: empty files should return None\n"
            "    return open(path).read()\n",
            encoding="utf-8",
        )
        git(repo, "add", "src/io.py")
        git(repo, "commit", "-m", "mid note", when="2025-06-01T12:00:00Z")

        (src / "app.py").write_text(
            f"# {TODO}: add a quiet flag\n"
            f'msg = "{TODO}: this string is not a comment"\n'
            "def main():\n"
            "    print(msg)\n",
            encoding="utf-8",
        )
        git(repo, "add", "src/app.py")
        git(repo, "commit", "-m", "new note", when="2026-11-01T12:00:00Z")

        r = subprocess.run([sys.executable, str(ROOT / "scan.py"), str(repo)])
        return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
