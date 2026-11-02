import hashlib
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "dep-scan.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=120)


def test_missing_manifests_reported_not_invented(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0
    assert "no package.json" in result.stdout
    assert "no requirements.txt" in result.stdout
    assert "upgrade list only" in result.stdout


def test_installed_package_reported_with_version(tmp_path):
    version = metadata.version("pytest")
    (tmp_path / "requirements.txt").write_text("pytest\n")
    result = run(tmp_path)
    assert result.returncode == 0
    assert f"installed {version}" in result.stdout


def test_nonexistent_package_reported_not_installed(tmp_path):
    (tmp_path / "requirements.txt").write_text("nonexistent-pkg-xyz-12345\n")
    result = run(tmp_path)
    assert result.returncode == 0
    assert "not installed here" in result.stdout


def test_check_latest_unknown_for_unknown_package(tmp_path):
    # Whether PyPI is reachable or not, an unknown package must not
    # get an invented latest version: it must be UNKNOWN.
    (tmp_path / "requirements.txt").write_text("nonexistent-pkg-xyz-12345\n")
    result = run(tmp_path, "--check-latest")
    assert result.returncode == 0
    assert "latest UNKNOWN, UNKNOWN" in result.stdout


def test_scan_changes_no_files(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("pytest\n")
    before = hashlib.sha256(req.read_bytes()).hexdigest()
    result = run(tmp_path)
    assert result.returncode == 0
    assert hashlib.sha256(req.read_bytes()).hexdigest() == before


def test_vulnerability_section_present_and_not_invented(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0
    assert "vulnerabilities:" in result.stdout
    # No CVE/GHSA id may appear for an empty project with no audits reporting.
    assert "CVE-" not in result.stdout
    assert "GHSA-" not in result.stdout


def test_demo_runs():
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "demo.py")],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0
    assert "not installed here" in result.stdout
