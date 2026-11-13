#!/usr/bin/env python3
"""Simple demo for hardcoded-path-scan: creates its own temp
directory, runs the grouped-table report, prints it, then cleans
up its temp dir.

Usage:
    python3 demo.py

It touches nothing outside its own temp directory, writes or
deletes no file, and only lists matched path fragments with file
and line number, never whole lines of source.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(
            prefix="hardcoded-path-scan-demo-") as tmp:
        repo = Path(tmp) / "demo-repo"
        repo.mkdir()
        (repo / "app.py").write_text(
            "#!/usr/bin/env python3\n"
            "DATA = \"C:/Users/demo/data.txt\"\n"
            "CONFIG = \"/home/demo/config.yaml\"\n"
            "SITE = \"https://example.com/docs\"\n",
            encoding="utf-8")
        (repo / "config.json").write_text(
            "{\"path\": \"/home/demo/settings\"}\n", encoding="utf-8")
        (repo / "notes.md").write_text(
            "See C:/Users/demo/secret\n", encoding="utf-8")
        print("=== hardcoded-path-scan on a temp demo repo ===",
              flush=True)
        subprocess.run([sys.executable,
                        str(HERE / "hardcoded-path-scan.py"),
                        str(repo)], check=True)
    print("\nDemo temp dir cleaned up. Nothing was changed or deleted.",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
