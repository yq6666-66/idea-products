from __future__ import annotations

import subprocess
from pathlib import Path

from preview import normalize_merged_branch_line


ROOT = Path(__file__).resolve().parents[1]


def test_strip_current_star_prefix():
    assert normalize_merged_branch_line("* main") == "main"
    assert normalize_merged_branch_line("*  feature/x") == "feature/x"


def test_strip_other_worktree_plus_prefix():
    assert normalize_merged_branch_line("+ feature") == "feature"
    assert normalize_merged_branch_line("+  work/a") == "work/a"


def test_plain_branch_unchanged():
    assert normalize_merged_branch_line("  topic") == "topic"
    assert normalize_merged_branch_line("topic") == "topic"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_cli_merged_section_handles_plus_prefix(tmp_path: Path):
    """Real git: branch checked out in another worktree shows '+ name' in --merged."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "init")
    _git(repo, "checkout", "-b", "feature")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-m", "feat")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "feature", "-m", "merge feature")
    wt = tmp_path / "wt-feature"
    _git(repo, "worktree", "add", str(wt), "feature")

    # sanity: git itself prints + prefix
    merged = subprocess.run(
        ["git", "-C", str(repo), "branch", "--merged", "main"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert any(line.strip().startswith("+ ") and "feature" in line for line in merged.splitlines())

    r = subprocess.run(
        ["python3", str(ROOT / "preview.py"), str(repo), "--base", "main"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "git log" not in r.stderr.lower()
    assert "failed" not in r.stderr.lower()
    # branch name appears without leading +
    assert "- feature" in r.stdout or "- feature " in r.stdout
    assert "+ feature" not in r.stdout
