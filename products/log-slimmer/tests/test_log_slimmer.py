import gzip
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "log-slimmer.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=60)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_log(directory, name, size, days_old):
    Path(directory).mkdir(parents=True, exist_ok=True)
    path = Path(directory) / name
    path.write_bytes(b"x" * size)
    stamp = time.time() - days_old * 86400
    os.utime(path, (stamp, stamp))
    return path


def test_report_sorts_by_size_desc(tmp_path):
    logs = tmp_path / "logs"
    make_log(logs, "small.log", 100, 1)
    make_log(logs, "big.log", 3000, 1)
    make_log(logs, "mid.log", 2000, 1)
    result = run(logs)
    assert result.returncode == 0
    assert "log files: 3" in result.stdout
    top = result.stdout.split("top 20 largest:")[1]
    assert top.index("big.log") < top.index("mid.log") < top.index("small.log")


def test_plan_flags_old_only_and_changes_nothing(tmp_path):
    logs = tmp_path / "logs"
    old = make_log(logs, "old.log", 500, 40)
    new = make_log(logs, "new.log", 500, 1)
    before = {p.name: sha(p) for p in (old, new)}
    result = run(logs, "--plan", "--older-than-days", "30")
    assert result.returncode == 0
    plan = result.stdout.split("PLAN:")[1]
    assert "old.log" in plan
    assert "new.log" not in plan
    assert {p.name: sha(p) for p in (old, new)} == before


def test_archive_without_confirm_refuses_and_changes_nothing(tmp_path):
    logs = tmp_path / "logs"
    old = make_log(logs, "old.log", 500, 40)
    before = sha(old)
    result = run(logs, "--archive", "--backup-dir", tmp_path / "bak",
                 "--archive-dir", tmp_path / "arc", "--older-than-days", "30")
    assert result.returncode == 2
    assert not (tmp_path / "bak").exists()
    assert not (tmp_path / "arc").exists()
    assert sha(old) == before


def test_archive_backup_first_and_original_untouched(tmp_path):
    logs = tmp_path / "logs"
    old = make_log(logs, "old.log", 2000, 40)
    before = sha(old)
    result = run(logs, "--archive", "--backup-dir", tmp_path / "bak",
                 "--archive-dir", tmp_path / "arc", "--confirm-archive",
                 "--older-than-days", "30")
    assert result.returncode == 0
    assert old.exists()
    assert sha(old) == before
    assert sha(tmp_path / "bak" / "old.log") == before
    assert gzip.open(tmp_path / "arc" / "old.log.gz", "rb").read() == old.read_bytes()


def test_archive_refuses_dirs_inside_scanned_dir(tmp_path):
    # Scanned dir is tmp_path itself, so bak/arc inside it must be refused.
    old = make_log(tmp_path, "old.log", 500, 40)
    before = sha(old)
    result = run(tmp_path, "--archive", "--backup-dir", tmp_path / "bak",
                 "--archive-dir", tmp_path / "arc", "--confirm-archive",
                 "--older-than-days", "30")
    assert result.returncode == 2
    assert sha(old) == before


def test_empty_directory(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    result = run(logs)
    assert result.returncode == 0
    assert "log files: 0" in result.stdout


def test_demo_runs_and_shows_plan():
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "demo.py")],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "big-old.log" in result.stdout
    assert "PLAN:" in result.stdout
