#!/usr/bin/env python3
"""Throwaway repo: merged branch, live worktree, prunable worktree. Then preview.py."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(cwd: Path, *args: str) -> None:
    r = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wt-preview-demo-") as tmp_name:
        tmp = Path(tmp_name)
        repo = tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.email", "demo@example.com")
        git(repo, "config", "user.name", "demo")
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(repo, "add", "a.txt")
        git(repo, "commit", "-m", "init")
        git(repo, "checkout", "-b", "feature")
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        git(repo, "add", "b.txt")
        git(repo, "commit", "-m", "feat")
        git(repo, "checkout", "main")
        git(repo, "merge", "--no-ff", "feature", "-m", "merge feature")
        git(repo, "worktree", "add", str(tmp / "wt-feature"), "feature")
        stale = tmp / "wt-stale"
        git(repo, "worktree", "add", "--detach", str(stale), "HEAD")
        shutil.rmtree(stale)
        r = subprocess.run(
            [sys.executable, str(ROOT / "preview.py"), str(repo), "--base", "main"],
        )
        return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
