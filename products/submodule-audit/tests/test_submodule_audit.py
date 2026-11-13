"""Tests for submodule-audit.py.

Builds one temporary root with eight repositories covering the
plan's eight self-test cases (origins live outside the scanned
root so they are not counted), then runs the script on it.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "submodule-audit.py"
FAKE_SHA = "1234567890abcdef1234567890abcdef12345678"


def git(directory, *args, allow_file=False):
    cmd = ["git", "-C", str(directory)]
    if allow_file:
        cmd += ["-c", "protocol.file.allow=always"]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=60)
    assert result.returncode == 0, (
        f"git {' '.join(args)} in {directory} failed: "
        f"{result.stderr}")
    return result


def init_repo(directory, files=None):
    directory.mkdir(parents=True, exist_ok=True)
    git(directory, "init", "-q", "-b", "main")
    git(directory, "config", "user.email", "test@example.invalid")
    git(directory, "config", "user.name", "Test")
    for name, text in (files or {}).items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(directory, "add", "-A")
    git(directory, "commit", "-qm", "init")
    return directory


def add_sub(parent, origin, name):
    git(parent, "submodule", "add", "-q", str(origin), name,
        allow_file=True)
    git(parent, "commit", "-qm", f"add {name}")


def build_fixture(base):
    origins = base / "origins"
    root = base / "root"
    sub_origin = init_repo(origins / "sub", {"f.txt": "sub\n"})
    nested_origin = init_repo(origins / "nested", {"g.txt": "nested\n"})
    carrier = init_repo(origins / "carrier", {"h.txt": "carrier\n"})
    add_sub(carrier, nested_origin, "nested")
    root.mkdir()
    healthy = init_repo(root / "healthy", {"a.txt": "a\n"})
    add_sub(healthy, sub_origin, "sub1")
    uninit = init_repo(root / "uninit", {"a.txt": "a\n"})
    add_sub(uninit, sub_origin, "sub1")
    git(uninit, "submodule", "deinit", "-q", "-f", "sub1")
    mismatch = init_repo(root / "mismatch", {"a.txt": "a\n"})
    add_sub(mismatch, sub_origin, "sub1")
    git(mismatch / "sub1", "config", "user.email",
        "test@example.invalid")
    git(mismatch / "sub1", "config", "user.name", "Test")
    (mismatch / "sub1" / "f.txt").write_text("sub changed\n")
    git(mismatch / "sub1", "add", "-A")
    git(mismatch / "sub1", "commit", "-qm", "local change")
    drift = init_repo(root / "drift", {"a.txt": "a\n"})
    add_sub(drift, sub_origin, "sub1")
    (drift / ".gitmodules").write_text(
        '[submodule "sub1"]\n\tpath = sub1\n'
        "\turl = /tmp/somewhere-else/sub\n",
        encoding="utf-8")
    nested = init_repo(root / "nested", {"a.txt": "a\n"})
    add_sub(nested, carrier, "outer")
    git(nested, "submodule", "update", "--init", "outer",
        allow_file=True)
    unreach = init_repo(root / "unreachable", {"a.txt": "a\n"})
    add_sub(unreach, sub_origin, "sub1")
    git(unreach, "config", "submodule.sub1.url",
        "/nonexistent/path-xyz")
    fake = init_repo(root / "fake-sha", {"a.txt": "a\n"})
    add_sub(fake, sub_origin, "sub1")
    result = subprocess.run(
        ["git", "-C", str(fake), "update-index", "--cacheinfo",
         f"160000,{FAKE_SHA},sub1"],
        capture_output=True, text=True)
    assert result.returncode == 0, (
        "update-index --cacheinfo must accept a fake SHA")
    init_repo(root / "empty", {"a.txt": "a\n"})
    (root / "plain").mkdir()
    (root / "plain" / "x.txt").write_text("x\n")
    init_repo(root / "node_modules" / "hidden-repo",
              {"a.txt": "a\n"})
    return root, sub_origin


@pytest.fixture(scope="module")
def fixture(tmp_path_factory):
    base = tmp_path_factory.mktemp("submodule-audit-fixture")
    return build_fixture(base)


def run_script(root, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root), *args],
        capture_output=True, text=True, timeout=180)


@pytest.fixture(scope="module")
def table_output(fixture):
    root, _origin = fixture
    result = run_script(root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def section(output, repo):
    parts = output.split(f"\n{repo}\n")
    assert len(parts) == 2, f"no section for {repo}"
    return parts[1].split("\n\n")[0]


def test_summary_counts(table_output):
    assert "共扫 8 个仓库，其中 7 个含子模块" in table_output


def test_hidden_and_plain_not_counted(table_output):
    assert "hidden-repo" not in table_output
    assert "plain" not in table_output


def test_empty_repo_not_listed(table_output):
    assert "empty" not in table_output.split("共扫")[0]


def test_healthy_not_reported(table_output):
    assert "\nhealthy\n" not in table_output


def test_uninitialized(table_output):
    rows = section(table_output, "uninit")
    assert "未初始化" in rows and "sub1" in rows


def test_mismatch(table_output):
    assert "提交不一致" in section(table_output, "mismatch")


def test_url_drift_and_config_unchanged(table_output, fixture):
    root, sub_origin = fixture
    assert "URL漂移" in section(table_output, "drift")
    url = subprocess.run(
        ["git", "-C", str(root / "drift"), "config", "--local",
         "--get", "submodule.sub1.url"],
        capture_output=True, text=True).stdout.strip()
    assert url == str(sub_origin)


def test_nested_uninitialized(table_output):
    rows = section(table_output, "nested")
    assert "outer/nested" in rows and "未初始化" in rows


def test_unreachable(table_output):
    assert "远端不可达" in section(table_output, "unreachable")


def test_remote_missing_commit(table_output):
    rows = section(table_output, "fake-sha")
    assert "远端不存在的提交" in rows
    assert "1234567" in rows


def test_severity_order(table_output):
    rows = section(table_output, "fake-sha")
    assert (rows.index("远端不存在的提交")
            < rows.index("提交不一致"))


def test_json_structure(fixture):
    root, _origin = fixture
    result = run_script(root, "--json")
    assert result.returncode == 0, result.stderr
    objects = json.loads(result.stdout)
    assert all(set(obj) == {"repo", "submodule", "level", "issue",
                            "suggestion"} for obj in objects)
    assert any(obj["repo"] == "fake-sha"
               and obj["level"] == "远端不存在的提交"
               for obj in objects)
    assert "共扫" in result.stderr
    assert "共扫" not in result.stdout


def test_read_only(fixture):
    root, _origin = fixture
    def hashes():
        return {
            str(p.relative_to(root)): hashlib.sha256(
                p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}
    before = hashes()
    run_script(root)
    assert hashes() == before


def test_missing_root_exit_2(tmp_path):
    result = run_script(tmp_path / "missing")
    assert result.returncode == 2
    assert "not a directory" in result.stderr
