"""Tests for gitignore-audit, run through subprocess because the
script filename contains a hyphen and cannot be imported."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "gitignore-audit.py"
DEMO = Path(__file__).resolve().parent.parent / "demo.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=30)


def run(directory, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(directory),
                           *args], capture_output=True, text=True,
                          timeout=30)


def make_repo(directory):
    directory.mkdir(parents=True, exist_ok=True)
    git(directory, "init", "-q")
    git(directory, "config", "user.email", "test@example.com")
    git(directory, "config", "user.name", "Test")
    (directory / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (directory / ".env").write_text("SECRET=x\n", encoding="utf-8")
    (directory / "old.log").write_text("old\n", encoding="utf-8")
    (directory / "keep.log").write_text("keep\n", encoding="utf-8")
    git(directory, "add", ".")
    git(directory, "commit", "-qm", "init")
    (directory / ".gitignore").write_text(
        ".env\n*.log\n!keep.log\n", encoding="utf-8")
    git(directory, "add", ".gitignore")
    git(directory, "commit", "-qm", "add gitignore")
    (directory / "build").mkdir(exist_ok=True)
    (directory / "build" / "output.txt").write_text("out\n",
                                                    encoding="utf-8")
    (directory / "new.py").write_text("print('new')\n", encoding="utf-8")
    return directory


def test_list_a_catches_tracked_ignored_with_rule_source(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    paths = [item["path"] for item in data["tracked_ignored"]]
    assert ".env" in paths
    assert "old.log" in paths
    env = next(item for item in data["tracked_ignored"]
               if item["path"] == ".env")
    assert env["rule"] == ".env"
    assert env["source_file"] == ".gitignore"
    assert env["source_line"] == 1
    assert "git rm --cached .env" in env["suggestion"]


def test_negation_and_normal_code_not_flagged(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    data = json.loads(result.stdout)
    paths = [item["path"] for item in data["tracked_ignored"]]
    assert "keep.log" not in paths
    assert "main.py" not in paths
    assert ".gitignore" not in paths


def test_list_b_catches_untracked_build_product_only(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    data = json.loads(result.stdout)
    paths = [item["path"] for item in data["untracked_suspected"]]
    assert "build/output.txt" in paths
    assert "new.py" not in paths
    item = next(i for i in data["untracked_suspected"]
                if i["path"] == "build/output.txt")
    assert "build" in item["suspected_type"]


def test_table_output_lists_both_lists(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo)
    assert result.returncode == 0
    assert ".env" in result.stdout
    assert "build/output.txt" in result.stdout
    assert "tracked_ignored: 2" in result.stdout
    assert "untracked_suspected: 1" in result.stdout


def test_json_summary_goes_to_stderr(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = run(repo, "--json")
    assert "tracked_ignored:" in result.stderr
    assert "tracked_ignored:" not in result.stdout


def test_missing_gitignore_list_a_empty_list_b_runs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "main.py").write_text("print('hi')\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "build").mkdir(exist_ok=True)
    (repo / "build" / "output.txt").write_text("out\n", encoding="utf-8")
    result = run(repo, "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["tracked_ignored"] == []
    assert [i["path"] for i in data["untracked_suspected"]] == [
        "build/output.txt"]
    assert "no .gitignore" in result.stderr


def test_scan_changes_nothing(tmp_path):
    repo = make_repo(tmp_path / "repo")
    before_status = git(repo, "status", "--porcelain").stdout
    before = {str(p.relative_to(repo)): hashlib.sha256(
        p.read_bytes()).hexdigest()
        for p in sorted(repo.rglob("*")) if p.is_file()
        and ".git" not in p.parts}
    run(repo)
    run(repo, "--json")
    after_status = git(repo, "status", "--porcelain").stdout
    after = {str(p.relative_to(repo)): hashlib.sha256(
        p.read_bytes()).hexdigest()
        for p in sorted(repo.rglob("*")) if p.is_file()
        and ".git" not in p.parts}
    assert after == before
    assert after_status == before_status


def test_non_git_directory_exits_2(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.txt").write_text("x\n", encoding="utf-8")
    result = run(plain)
    assert result.returncode == 2
    assert "not a git repository" in result.stderr


def test_demo_runs_and_shows_both_lists(tmp_path):
    result = subprocess.run([sys.executable, str(DEMO)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert ".env" in result.stdout
    assert "build/output.txt" in result.stdout
