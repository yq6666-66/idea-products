#!/usr/bin/env python3
"""Simple demo for gitignore-audit: creates its own temp git repo,
runs the two-list report, prints it, then cleans up its temp dir.

Usage:
    python3 demo.py

It touches nothing outside its own temp directory, writes no
.gitignore, deletes no file, and only lists paths, never contents.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True, timeout=30)


def main():
    with tempfile.TemporaryDirectory(prefix="gitignore-audit-demo-") as tmp:
        repo = Path(tmp) / "demo-repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "demo@example.com")
        git(repo, "config", "user.name", "Demo")
        (repo / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (repo / ".env").write_text("SECRET=x\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "init")
        (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
        git(repo, "add", ".gitignore")
        git(repo, "commit", "-qm", "add gitignore")
        (repo / "build").mkdir()
        (repo / "build" / "output.txt").write_text("out\n",
                                                   encoding="utf-8")
        print("=== gitignore-audit on a temp demo repo ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "gitignore-audit.py"),
                        str(repo)], check=True)
    print("\nDemo temp dir cleaned up. Nothing was changed or deleted.",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
