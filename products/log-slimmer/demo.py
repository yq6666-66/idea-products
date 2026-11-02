#!/usr/bin/env python3
"""Simple demo for log-slimmer: creates its own temp logs, runs the
report and the --plan, prints both, then cleans up its temp dir.

Usage:
    python3 demo.py

It touches nothing outside its own temp directory.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def make_log(directory, name, size, days_old):
    path = Path(directory) / name
    path.write_bytes(b"x" * size)
    stamp = time.time() - days_old * 86400
    os.utime(path, (stamp, stamp))
    return path


def main():
    with tempfile.TemporaryDirectory(prefix="log-slimmer-demo-") as tmp:
        logs = Path(tmp) / "logs"
        logs.mkdir()
        make_log(logs, "big-old.log", 3000, 40)
        make_log(logs, "mid-old.log", 2000, 35)
        make_log(logs, "small-new.log", 100, 1)
        print("=== report ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "log-slimmer.py"), str(logs)],
                       check=True)
        print("\n=== plan (older than 30 days, nothing changed) ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "log-slimmer.py"), str(logs),
                        "--plan", "--older-than-days", "30"], check=True)
    print("\nDemo temp dir cleaned up. Originals were never touched.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
