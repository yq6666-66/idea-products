#!/usr/bin/env python3
"""Simple demo for dep-scan: creates its own temp project, runs the
report, prints it, then cleans up its temp dir.

Usage:
    python3 demo.py

It touches nothing outside its own temp directory and upgrades nothing.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix="dep-scan-demo-") as tmp:
        proj = Path(tmp) / "demo-project"
        proj.mkdir()
        (proj / "requirements.txt").write_text(
            "pip\nnonexistent-pkg-demo-12345\n", encoding="utf-8")
        print("=== dep-scan on a temp demo project ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "dep-scan.py"), str(proj)],
                       check=True)
    print("\nDemo temp dir cleaned up. Nothing was upgraded.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
