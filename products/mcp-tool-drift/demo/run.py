#!/usr/bin/env python3
"""Self-contained demo. No network and no real MCP server.

Uses the fake home under demo/home, a mock tool catalogue, and demo/fake_mcp.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli.py"
SECRET = "sample-not-a-secret"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def show(title: str, result: subprocess.CompletedProcess[str]) -> None:
    print(f"== {title} (exit {result.returncode}) ==")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)


def main() -> int:
    discovered = run(["discover", "--root", str(ROOT / "demo" / "home")])
    show("discover", discovered)
    if discovered.returncode != 0 or "demo-fs" not in discovered.stdout or "demo-notes" not in discovered.stdout:
        return 1
    if SECRET in discovered.stdout + discovered.stderr:
        return 1

    offline = run(["offline", "--config", "demo/cursor-mcp.good.json"])
    show("offline", offline)
    if offline.returncode != 0:
        return 1
    bad = run(["offline", "--config", "demo/cursor-mcp.bad.json"])
    show("offline bad json", bad)
    if bad.returncode != 2:
        return 1

    with tempfile.TemporaryDirectory(prefix="mcp-tool-drift-demo-") as tmp_name:
        tmp = Path(tmp_name)
        mock_out = tmp / "mock.json"
        stdio_out = tmp / "stdio.json"
        mocked = run(
            [
                "online",
                "--config",
                "demo/cursor-mcp.good.json",
                "--transport",
                "mock",
                "--mock-tools",
                "demo/mock-tools.json",
                "--timeout",
                "5",
                "--out",
                str(mock_out),
            ]
        )
        show("online mock", mocked)
        if mocked.returncode != 0 or SECRET in mocked.stdout + mocked.stderr:
            return 1
        mock_snap = json.loads(mock_out.read_text(encoding="utf-8"))
        print(f"mock servers: {', '.join(sorted(mock_snap['servers']))}")

        stdio = run(
            [
                "online",
                "--config",
                "demo/stdio-mcp.json",
                "--transport",
                "stdio",
                "--timeout",
                "5",
                "--out",
                str(stdio_out),
            ]
        )
        show("online stdio fake", stdio)
        if stdio.returncode != 0 or SECRET in stdio.stdout + stdio.stderr:
            return 1
        stdio_snap = json.loads(stdio_out.read_text(encoding="utf-8"))
        print(f"stdio tools: {', '.join(sorted(stdio_snap))}")

    diff = run(["diff", "--before", "demo/snapshot-a.json", "--after", "demo/snapshot-b.json"])
    show("diff", diff)
    if diff.returncode != 1:
        return 1
    warned = run(
        ["diff", "--before", "demo/snapshot-a.json", "--after", "demo/snapshot-b.json", "--warn-only"]
    )
    show("diff --warn-only", warned)
    if warned.returncode != 0 or warned.stdout != diff.stdout:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
