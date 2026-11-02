from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scan import in_comment, is_testish, looks_like_string_literal_hit, MARKER_RE


ROOT = Path(__file__).resolve().parents[1]


def test_comment_hits():
    assert in_comment("// TODO fix")
    assert in_comment("# FIXME later")
    assert in_comment("    * TODO in block")
    assert in_comment("code // TODO trailing")


def test_string_literal_skipped():
    line = 'assert "TODO fake" in msg'
    assert MARKER_RE.search(line)
    assert looks_like_string_literal_hit(line)
    assert not in_comment(line)


def test_test_paths_default_skip():
    assert is_testish(Path("tests/test_foo.py"))
    assert is_testish(Path("src/__tests__/a.js"))
    assert is_testish(Path("pkg/fixtures/x.md"))
    assert not is_testish(Path("src/main.py"))


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "src" / "a.js").write_text('// TODO real\nconst x = "TODO fake";\n', encoding="utf-8")
    (repo / "tests" / "t.js").write_text('assert("TODO");\n# TODO in test comment\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_cli_default_skips_tests_and_literals(tmp_path: Path):
    repo = _init_repo(tmp_path)
    r = subprocess.run(
        ["python3", str(ROOT / "scan.py"), str(repo)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "count: 1" in r.stdout
    assert "src/a.js:1" in r.stdout
    assert "TODO fake" not in r.stdout
    assert "tests/t.js" not in r.stdout


def test_cli_include_tests_keeps_test_comments(tmp_path: Path):
    repo = _init_repo(tmp_path)
    r = subprocess.run(
        ["python3", str(ROOT / "scan.py"), str(repo), "--include-tests"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "count: 2" in r.stdout
    assert "tests/t.js:2" in r.stdout
    assert 'assert("TODO")' not in r.stdout
