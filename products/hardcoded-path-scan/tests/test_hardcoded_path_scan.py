"""Tests for hardcoded-path-scan, run through subprocess because
the script filename contains a hyphen and cannot be imported."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hardcoded-path-scan.py"
DEMO = Path(__file__).resolve().parent.parent / "demo.py"
BS = chr(92)
DRIVE_PATH = "C:/Users/demo/data.txt"
UNC_PATH = BS * 2 + "server" + BS + "share" + BS + "file.txt"


def run(directory, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(directory),
                           *args], capture_output=True, text=True,
                          timeout=30)


def make_repo(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "app.py").write_text(
        "#!/usr/bin/env python3\n"
        "DATA = \"C:/Users/demo/data.txt\"\n"
        "CONFIG = \"/home/demo/config.yaml\"\n"
        "SITE = \"https://example.com/docs\"\n",
        encoding="utf-8")
    (directory / "config.json").write_text(
        "{\"path\": \"/home/demo/settings\"}\n", encoding="utf-8")
    (directory / "notes.md").write_text(
        "See C:/Users/demo/secret\n", encoding="utf-8")
    (directory / "share.js").write_text(
        "const f = \"" + UNC_PATH + "\";\n", encoding="utf-8")
    return directory


def test_drive_and_posix_caught_with_kinds(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    by_path = {item["path"]: item for item in data}
    assert by_path[DRIVE_PATH]["kind"] == "盘符"
    assert by_path["/home/demo/config.yaml"]["kind"] == "POSIX"
    assert by_path["/home/demo/settings"]["kind"] == "POSIX"
    assert by_path[DRIVE_PATH]["file"] == "app.py"
    assert by_path[DRIVE_PATH]["line"] == 2


def test_unc_caught(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    data = json.loads(result.stdout)
    by_path = {item["path"]: item for item in data}
    assert by_path[UNC_PATH]["kind"] == "UNC"


def test_shebang_url_and_md_not_flagged(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    data = json.loads(result.stdout)
    paths = [item["path"] for item in data]
    assert "/usr/bin/env" not in paths
    assert not any("example.com" in p for p in paths)
    assert not any("secret" in p for p in paths)
    assert all(item["file"] != "notes.md" for item in data)


def test_same_file_multi_line_hits_listed_separately(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    data = json.loads(result.stdout)
    app_hits = [item for item in data if item["file"] == "app.py"]
    assert [item["line"] for item in app_hits] == [2, 3]
    assert len(app_hits) == 2


def test_table_output_groups_by_file(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo)
    assert result.returncode == 0
    assert "app.py" in result.stdout
    assert DRIVE_PATH in result.stdout
    assert "/home/demo/settings" in result.stdout
    assert "scanned: 3 file(s), hits: 4" in result.stdout


def test_json_summary_goes_to_stderr(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    assert "scanned:" in result.stderr
    assert "scanned:" not in result.stdout


def test_binary_py_file_skipped(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "bad.py").write_bytes(
        b"DATA = \"C:/Users/demo/x\"\x00\n")
    result = run(repo, "--json")
    data = json.loads(result.stdout)
    assert all(item["file"] != "bad.py" for item in data)
    assert "binary: 1" in result.stderr


def test_scan_changes_nothing(tmp_path):
    repo = make_repo(tmp_path / "repo")
    before = {str(p.relative_to(repo)): hashlib.sha256(
        p.read_bytes()).hexdigest()
        for p in sorted(repo.rglob("*")) if p.is_file()}
    run(repo)
    run(repo, "--json")
    after = {str(p.relative_to(repo)): hashlib.sha256(
        p.read_bytes()).hexdigest()
        for p in sorted(repo.rglob("*")) if p.is_file()}
    assert after == before


def test_missing_directory_exits_2(tmp_path):
    result = run(tmp_path / "no-such-dir")
    assert result.returncode == 2
    assert "not a directory" in result.stderr


def test_demo_runs_and_shows_hits(tmp_path):
    result = subprocess.run([sys.executable, str(DEMO)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert DRIVE_PATH in result.stdout
    assert "/home/demo/settings" in result.stdout
