"""Tests for startup-cmds, run through subprocess because the
script filename contains a hyphen and cannot be imported."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "startup-cmds.py"
DEMO = Path(__file__).resolve().parent.parent / "demo.py"


def run(directory, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(directory),
                           *args], capture_output=True, text=True,
                          timeout=30)


def make_project(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite",
                                "build": "tsc && vite build",
                                "test": "vitest"}}), encoding="utf-8")
    (directory / "Makefile").write_text(
        "build: deps\n\techo building\n\ntest: # run tests\n\techo testing\n\n"
        ".PHONY: build test\n\n%.o: %.c\n\tcc -c $<\n\nAPP = myapp\n",
        encoding="utf-8")
    (directory / "justfile").write_text(
        'serve host="localhost" port="8000":\n  echo serving\n\n'
        "_private:\n  echo secret\n\nbuild:\n  echo building\n",
        encoding="utf-8")
    (directory / "pyproject.toml").write_text(
        '[project.scripts]\nstart = "app:main"\n\n'
        '[tool.poetry.scripts]\nold = "app:old"\n', encoding="utf-8")


def test_table_lists_all_commands_without_merging(tmp_path):
    proj = tmp_path / "proj"
    make_project(proj)
    result = run(proj)
    assert result.returncode == 0
    for needle in ("vite", "tsc && vite build", "vitest", "make test",
                   "run tests", "just serve <host> <port>", "app:main",
                   "app:old"):
        assert needle in result.stdout
    # build appears once per file (package.json, Makefile, justfile)
    assert result.stdout.count("build") >= 3
    assert "scanned: 4 file(s), commands: 9" in result.stdout


def test_private_pattern_and_phony_excluded(tmp_path):
    proj = tmp_path / "proj"
    make_project(proj)
    result = run(proj)
    assert "_private" not in result.stdout
    assert "%.o" not in result.stdout
    assert ".PHONY" not in result.stdout


def test_broken_and_missing_files_reported_not_invented(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text("{broken json", encoding="utf-8")
    (proj / "pyproject.toml").write_text('[project]\nname = "x"\n',
                                         encoding="utf-8")
    result = run(proj)
    assert result.returncode == 0
    assert "skipped package.json: unreadable" in result.stdout
    assert "skipped Makefile: missing" in result.stdout
    assert "skipped justfile: missing" in result.stdout
    assert "note pyproject.toml: no scripts table" in result.stdout
    assert "commands: 0" in result.stdout


def test_json_output_is_array_and_summary_goes_to_stderr(tmp_path):
    proj = tmp_path / "proj"
    make_project(proj)
    result = run(proj, "--json")
    assert result.returncode == 0
    objects = json.loads(result.stdout)
    assert len(objects) == 9
    assert any(o["name"] == "serve <host> <port>"
               and o["command"] == "just serve <host> <port>"
               for o in objects)
    assert "scanned:" in result.stderr
    assert "scanned:" not in result.stdout


def test_scanning_changes_no_files(tmp_path):
    proj = tmp_path / "proj"
    make_project(proj)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(proj.iterdir()) if p.is_file()}
    run(proj)
    run(proj, "--json")
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(proj.iterdir()) if p.is_file()}
    assert after == before


def test_missing_directory_exits_nonzero(tmp_path):
    result = run(tmp_path / "no-such-dir")
    assert result.returncode == 2


def test_demo_runs_and_shows_commands(tmp_path):
    result = subprocess.run([sys.executable, str(DEMO)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "vite" in result.stdout
    assert "scanned:" in result.stdout
