from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli.py"
DEMO = ROOT / "demo"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_offline_good_lists_servers():
    r = _run(["offline", "--config", str(DEMO / "cursor-mcp.good.json")])
    assert r.returncode == 0, r.stderr
    names = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    assert names == ["demo-fs", "demo-search"]
    assert "sample-not-a-secret" not in r.stdout
    assert "sample-not-a-secret" not in r.stderr


def test_offline_bad_json_exits_2():
    r = _run(["offline", "--config", str(DEMO / "cursor-mcp.bad.json")])
    assert r.returncode == 2
    assert r.stdout.strip() == ""
    assert "JSON" in r.stderr or "json" in r.stderr


def test_diff_reports_added_removed_breaking_and_exits_1():
    r = _run(
        [
            "diff",
            "--before",
            str(DEMO / "snapshot-a.json"),
            "--after",
            str(DEMO / "snapshot-b.json"),
        ]
    )
    assert r.returncode == 1, r.stderr
    text = r.stdout
    assert "added:\n  list_tools\n" in text
    assert "removed:\n  legacy_ping\n" in text
    assert "breaking:\n  search\n" in text
    assert "unchanged:\n  echo\n" in text
    assert "legacy_ping" not in text.split("added:", 1)[1].split("removed:", 1)[0]


def test_diff_warn_only_exits_0():
    r = _run(
        [
            "diff",
            "--before",
            str(DEMO / "snapshot-a.json"),
            "--after",
            str(DEMO / "snapshot-b.json"),
            "--warn-only",
        ]
    )
    assert r.returncode == 0, r.stderr
    assert "added:\n  list_tools\n" in r.stdout
    assert "removed:\n  legacy_ping\n" in r.stdout
    assert "breaking:\n  search\n" in r.stdout


def test_diff_clean_exits_0(tmp_path: Path):
    snap = {
        "echo": {"schema_hash": "aaa111", "description_hash": "d1"},
    }
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(snap), encoding="utf-8")
    after.write_text(json.dumps(snap), encoding="utf-8")
    r = _run(["diff", "--before", str(before), "--after", str(after)])
    assert r.returncode == 0, r.stderr
    assert "added:\n  (none)\n" in r.stdout
    assert "removed:\n  (none)\n" in r.stdout
    assert "breaking:\n  (none)\n" in r.stdout
    assert "unchanged:\n  echo\n" in r.stdout


def test_description_hash_change_is_not_breaking(tmp_path: Path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(
        json.dumps({"echo": {"schema_hash": "aaa111", "description_hash": "d1"}}),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps({"echo": {"schema_hash": "aaa111", "description_hash": "d9"}}),
        encoding="utf-8",
    )
    r = _run(["diff", "--before", str(before), "--after", str(after)])
    assert r.returncode == 0, r.stderr
    assert "breaking:\n  (none)\n" in r.stdout
    assert "unchanged:\n  echo\n" in r.stdout
