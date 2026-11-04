#!/usr/bin/env python3
"""Simple demo for startup-cmds: creates its own temp project,
runs the table report, prints it, then cleans up its temp dir.

Usage:
    python3 demo.py

It touches nothing outside its own temp directory, executes
nothing from the demo project, and changes no files.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix="startup-cmds-demo-") as tmp:
        proj = Path(tmp) / "demo-project"
        proj.mkdir()
        (proj / "package.json").write_text(
            json.dumps({"scripts": {"dev": "vite",
                                    "build": "tsc && vite build"}}),
            encoding="utf-8")
        (proj / "Makefile").write_text(
            "build:\n\techo building\n\ntest: # run tests\n\techo testing\n",
            encoding="utf-8")
        (proj / "justfile").write_text(
            'serve host="localhost":\n  echo serving\n', encoding="utf-8")
        (proj / "pyproject.toml").write_text(
            '[project.scripts]\nstart = "app:main"\n', encoding="utf-8")
        print("=== startup-cmds on a temp demo project ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "startup-cmds.py"),
                        str(proj)], check=True)
    print("\nDemo temp dir cleaned up. Nothing was executed or changed.",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
