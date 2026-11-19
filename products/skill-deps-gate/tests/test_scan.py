"""Directory scan behavior."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_OK = "fixtures/snapshots/scan-ok.json"
HEADER = "技能\t路径\t依赖\t种类\t状态"


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "skill_deps_gate", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def matrix(stdout: str) -> list[list[str]]:
    lines = stdout.splitlines()
    assert lines and lines[0] == HEADER, stdout
    return [line.split("\t") for line in lines[1:]]


class ScanTests(unittest.TestCase):
    def test_one_root_reports_skills_in_path_order_and_exits_0(self) -> None:
        proc = run_cli(["--skill", "fixtures/roots/ok", "--snapshot", SCAN_OK])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(
            [row[1] for row in matrix(proc.stdout)],
            [
                "fixtures/roots/ok/alpha",
                "fixtures/roots/ok/alpha",
                "fixtures/roots/ok/beta",
                "fixtures/roots/ok/beta",
            ],
        )
        self.assertIn(["alpha", "fixtures/roots/ok/alpha", "search", "tools.all", "满足"], matrix(proc.stdout))
        self.assertIn(["beta", "fixtures/roots/ok/beta", "fetch", "tools.all", "满足"], matrix(proc.stdout))

    def test_two_roots_keep_argument_order(self) -> None:
        proc = run_cli(
            [
                "--skill",
                "fixtures/roots/ok",
                "--skill",
                "fixtures/roots/extra",
                "--snapshot",
                SCAN_OK,
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        paths = [row[1] for row in matrix(proc.stdout)]
        self.assertEqual(
            paths,
            [
                "fixtures/roots/ok/alpha",
                "fixtures/roots/ok/alpha",
                "fixtures/roots/ok/beta",
                "fixtures/roots/ok/beta",
                "fixtures/roots/extra/gamma",
                "fixtures/roots/extra/gamma",
                "fixtures/roots/extra/gamma",
            ],
        )

    def test_missing_skill_is_not_hidden_by_a_passing_skill(self) -> None:
        proc = run_cli(["--skill", "fixtures/roots/mixed", "--snapshot", SCAN_OK])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        rows = matrix(proc.stdout)
        self.assertIn(["good", "fixtures/roots/mixed/good", "search", "tools.all", "满足"], rows)
        self.assertIn(["bad", "fixtures/roots/mixed/bad", "absenttool", "tools.all", "缺失"], rows)
        self.assertIn("unsatisfied: fixtures/roots/mixed/bad: absenttool", proc.stderr)

    def test_duplicate_names_stay_distinct_and_sorted(self) -> None:
        proc = run_cli(["--skill", "fixtures/roots/dup", "--snapshot", SCAN_OK])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = matrix(proc.stdout)
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows if row[3] == "tools.all"],
            [
                ("shared", "fixtures/roots/dup/a", "search"),
                ("shared", "fixtures/roots/dup/b", "fetch"),
            ],
        )

    def test_empty_directory_is_an_input_error(self) -> None:
        empty = Path(tempfile.mkdtemp(prefix="sdg-empty-"))
        proc = run_cli(["--skill", str(empty), "--snapshot", SCAN_OK])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("没有找到 SKILL.md", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def test_symlink_escape_is_refused(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-link-"))
        root = base / "root"
        outside = base / "outside"
        (root / "kept").mkdir(parents=True)
        outside.mkdir()
        (root / "kept" / "SKILL.md").write_text(
            "---\nname: kept\ndependencies:\n  tools:\n    all:\n      - search\nrequires-mcp-servers:\n  - docs\n---\n\nBODY_MARKER_DO_NOT_EXECUTE\n",
            encoding="utf-8",
        )
        (outside / "SKILL.md").write_text(
            "---\nname: escaped-skill\ndependencies:\n  tools:\n    all:\n      - search\nrequires-mcp-servers:\n  - docs\n---\n\n",
            encoding="utf-8",
        )
        (root / "escape").symlink_to(outside, target_is_directory=True)
        proc = run_cli(["--skill", str(root), "--snapshot", SCAN_OK])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("escaped-skill", proc.stdout)
        self.assertNotIn("escaped-skill", proc.stderr)
        self.assertIn("符号链接不允许", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_skill_directory_symlink_is_refused(self) -> None:
        base = self._linked_skill_tree()
        proc = self._run_at(base, ["--skill", "symlink-skill", "--snapshot", "scan-ok.json"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        self.assertIn("符号链接不允许", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertFalse((base / "real-skill" / "SHOULD_NOT_EXIST").exists())

    def test_broken_skill_symlink_is_refused(self) -> None:
        base = self._linked_skill_tree()
        proc = self._run_at(base, ["--skill", "broken-skill", "--snapshot", "scan-ok.json"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("符号链接不允许", proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_symlink_ancestor_and_dotdot_are_refused(self) -> None:
        base = self._linked_skill_tree()
        for skill in ("ancestor-link/child", "symlink-skill/../real-skill"):
            with self.subTest(skill=skill):
                proc = self._run_at(base, ["--skill", skill, "--snapshot", "scan-ok.json"])
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertNotIn("满足", proc.stdout)
                self.assertIn("符号链接不允许", proc.stderr)

    def test_real_skill_mixed_with_symlink_stays_exit_2(self) -> None:
        base = self._linked_skill_tree()
        proc = self._run_at(
            base,
            ["--skill", "real-skill", "--skill", "symlink-skill", "--snapshot", "scan-ok.json"],
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        self.assertIn("未判定", proc.stdout)
        self.assertIn("符号链接不允许", proc.stderr)
        repeated = self._run_at(
            base,
            ["--skill", "symlink-skill", "--skill", "broken-skill", "--snapshot", "scan-ok.json"],
        )
        self.assertEqual(repeated.returncode, 2, repeated.stderr)
        self.assertEqual(repeated.stdout, "")
        self.assertNotIn("满足", repeated.stdout)

    def test_scan_error_keeps_discovered_skill_as_undecided(self) -> None:
        parent = Path(tempfile.mkdtemp(prefix="sdg-keep-"))
        base = parent / "root"
        base.mkdir()
        kept = base / "kept"
        kept.mkdir()
        kept.joinpath("SKILL.md").write_text(
            "---\nname: kept\ndependencies:\n  tools:\n    all:\n      - search\nrequires-mcp-servers:\n  - docs\n---\n\nBODY_MARKER_DO_NOT_EXECUTE\n",
            encoding="utf-8",
        )
        outside = parent / "outside"
        outside.mkdir()
        outside.joinpath("SKILL.md").write_text(
            "---\nname: escaped-skill\ndependencies:\n  tools:\n    all:\n      - search\n---\n\n",
            encoding="utf-8",
        )
        (base / "escape").symlink_to(outside, target_is_directory=True)
        proc = self._run_at(base, ["--skill", ".", "--snapshot", str(ROOT / "fixtures" / "snapshots" / "scan-ok.json")])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("符号链接不允许", proc.stderr)
        self.assertIn("未判定", proc.stdout)
        self.assertNotIn("满足", proc.stdout)
        self.assertNotIn("escaped-skill", proc.stdout)
        self.assertIn("kept", proc.stdout)

    def test_snapshot_through_directory_symlink_is_refused(self) -> None:
        base = self._linked_skill_tree()
        proc = self._run_at(base, ["--skill", "real-skill", "--snapshot", "snap-link/scan-ok.json"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("快照路径不允许符号链接", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def test_unreadable_directory_is_an_input_error(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root can read mode 000 directories")
        blocked = Path(tempfile.mkdtemp(prefix="sdg-mode-"))
        blocked.chmod(0)
        try:
            proc = run_cli(["--skill", str(blocked), "--snapshot", SCAN_OK])
        finally:
            blocked.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("目录不可读", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def _linked_skill_tree(self) -> Path:
        base = Path(tempfile.mkdtemp(prefix="sdg-root-link-"))
        real = base / "real-skill"
        real.mkdir()
        real.joinpath("SKILL.md").write_text(
            "---\nname: real-skill\ndependencies:\n  tools:\n    all:\n      - search\n"
            "requires-mcp-servers:\n  - docs\n---\n\nBODY_MARKER_DO_NOT_EXECUTE\ntouch SHOULD_NOT_EXIST\n",
            encoding="utf-8",
        )
        (base / "symlink-skill").symlink_to("real-skill", target_is_directory=True)
        (base / "broken-skill").symlink_to("missing-target", target_is_directory=True)
        target = base / "ancestor-link-target" / "child"
        target.mkdir(parents=True)
        target.joinpath("SKILL.md").write_text(
            (real / "SKILL.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (base / "ancestor-link").symlink_to("ancestor-link-target", target_is_directory=True)
        (base / "scan-ok.json").write_bytes((ROOT / SCAN_OK).read_bytes())
        snap_real = base / "snap-real"
        snap_real.mkdir()
        (snap_real / "scan-ok.json").write_bytes((ROOT / SCAN_OK).read_bytes())
        (base / "snap-link").symlink_to("snap-real", target_is_directory=True)
        return base

    def _run_at(self, cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
        return subprocess.run(
            [sys.executable, "-m", "skill_deps_gate", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
