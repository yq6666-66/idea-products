from __future__ import annotations

import subprocess
from pathlib import Path

from check import check_local, extract_links


ROOT = Path(__file__).resolve().parents[1]


def test_extract_markdown_links():
    assert extract_links("[a](./x.md) and [b](https://example.com)") == [
        "./x.md",
        "https://example.com",
    ]


def test_check_local_missing_is_dead(tmp_path: Path):
    md = tmp_path / "doc.md"
    md.write_text("x", encoding="utf-8")
    status, detail = check_local(tmp_path, md, "./missing.md")
    assert status == "dead"
    assert detail == "missing-file"


def test_check_local_exists_is_ok(tmp_path: Path):
    (tmp_path / "ok.md").write_text("ok", encoding="utf-8")
    md = tmp_path / "doc.md"
    md.write_text("x", encoding="utf-8")
    status, detail = check_local(tmp_path, md, "./ok.md")
    assert status == "ok"


def _write_broken_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("[gone](./nope.md)\n", encoding="utf-8")
    return repo


def test_cli_default_exit_1_on_local_broken(tmp_path: Path):
    repo = _write_broken_repo(tmp_path)
    r = subprocess.run(
        ["python3", str(ROOT / "check.py"), str(repo)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "## broken" in r.stdout
    assert "./nope.md" in r.stdout


def test_cli_warn_only_exit_0_on_local_broken(tmp_path: Path):
    repo = _write_broken_repo(tmp_path)
    r = subprocess.run(
        ["python3", str(ROOT / "check.py"), str(repo), "--warn-only"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "## broken" in r.stdout
    assert "./nope.md" in r.stdout


def test_cli_clean_repo_exit_0(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ok.md").write_text("hi\n", encoding="utf-8")
    (repo / "README.md").write_text("[ok](./ok.md)\n", encoding="utf-8")
    r = subprocess.run(
        ["python3", str(ROOT / "check.py"), str(repo)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "no broken links found." in r.stdout
