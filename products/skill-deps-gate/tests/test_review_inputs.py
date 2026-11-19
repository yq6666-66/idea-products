"""Input-validation cases from the 2026-11-12 review. Written to fail first."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_OK = ROOT / "fixtures" / "snapshots" / "scan-ok.json"
OTHER = ROOT / "fixtures" / "snapshots" / "any-on-other.json"
ONE_MIB = 1024 * 1024


def run_cli(args: list[str], cwd: Path | None = None, timeout: float = 2) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    return subprocess.run(
        [sys.executable, "-m", "skill_deps_gate", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


class ReviewInputTests(unittest.TestCase):
    def test_indented_delimiter_does_not_drop_server_binding(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-delim-"))
        skill = base / "trunc"
        skill.mkdir()
        skill.joinpath("SKILL.md").write_text(
            "---\n"
            "name: trunc\n"
            "dependencies:\n"
            "  tools:\n"
            "    all:\n"
            "      - search\n"
            "description: |\n"
            "  note\n"
            "  ---\n"
            "  still description\n"
            "requires-mcp-servers:\n"
            "  - docs\n"
            "---\n"
            "\nBODY_MARKER_DO_NOT_EXECUTE\n",
            encoding="utf-8",
        )
        proc = run_cli(["--skill", str(skill), "--snapshot", str(OTHER)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("docs", proc.stdout)
        self.assertIn("缺失", proc.stdout)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unsatisfied: search", proc.stderr)

    def test_snapshot_version_must_be_int_one(self) -> None:
        base = json.loads(SCAN_OK.read_text(encoding="utf-8"))
        for label, version in (("float", 1.0), ("bool", True)):
            with self.subTest(label=label):
                path = Path(tempfile.mkdtemp(prefix="sdg-ver-")) / "snap.json"
                payload = dict(base)
                payload["skill_deps_gate_snapshot"] = version
                path.write_text(json.dumps(payload), encoding="utf-8")
                skill = self._ok_skill()
                proc = run_cli(["--skill", str(skill), "--snapshot", str(path)])
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertNotIn("满足", proc.stdout)
                self.assertIn("样本封装", proc.stderr)

    def test_nested_unreadable_directory_is_not_a_pass(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root can read mode 000 directories")
        base = Path(tempfile.mkdtemp(prefix="sdg-lock-"))
        ok = base / "ok"
        ok.mkdir()
        ok.joinpath("SKILL.md").write_text(self._ok_text(), encoding="utf-8")
        locked = base / "locked"
        locked.mkdir()
        locked.chmod(0)
        try:
            proc = run_cli(["--skill", str(base), "--snapshot", str(SCAN_OK)])
        finally:
            locked.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("目录不可读", proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        self.assertIn("未判定", proc.stdout)

    def test_size_limit_is_one_mebibyte(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-size-"))
        under = base / "under"
        under.mkdir()
        under.joinpath("SKILL.md").write_bytes(b"x" * (1_000_001))
        proc = run_cli(["--skill", str(under), "--snapshot", str(SCAN_OK)])
        self.assertNotIn("过大", proc.stderr)
        self.assertNotEqual(proc.returncode, 0)
        over = base / "over"
        over.mkdir()
        over.joinpath("SKILL.md").write_bytes(b"x" * (ONE_MIB + 1))
        proc = run_cli(["--skill", str(over), "--snapshot", str(SCAN_OK)])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("过大", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def test_fifo_skill_and_snapshot_do_not_hang(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-fifo-"))
        skill = base / "fifo-skill"
        skill.mkdir()
        os.mkfifo(skill / "SKILL.md")
        proc = run_cli(["--skill", str(skill), "--snapshot", str(SCAN_OK)])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("不是普通文件", proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        snap = base / "snap.fifo"
        os.mkfifo(snap)
        ok = self._ok_skill()
        proc = run_cli(["--skill", str(ok), "--snapshot", str(snap)])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("不是普通文件", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def test_license_metadata_is_ignored_and_unknown_dependency_is_not(self) -> None:
        skill = Path(tempfile.mkdtemp(prefix="sdg-lic-")) / "licensed"
        skill.mkdir()
        skill.joinpath("SKILL.md").write_text(
            "---\nname: licensed\nlicense: MIT\ncompatibility: fictional\n"
            "metadata:\n  owner: example\nallowed-tools: search\n"
            "dependencies:\n  tools:\n    all:\n      - search\n"
            "requires-mcp-servers:\n  - docs\n---\n\nBODY_MARKER_DO_NOT_EXECUTE\n",
            encoding="utf-8",
        )
        proc = run_cli(["--skill", str(skill), "--snapshot", str(SCAN_OK)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("满足", proc.stdout)
        unknown = Path(tempfile.mkdtemp(prefix="sdg-unk-")) / "unknown"
        unknown.mkdir()
        unknown.joinpath("SKILL.md").write_text(
            "---\nname: unknown\ndependencies:\n  tools:\n    all:\n      - search\n    extra:\n      - search\n---\n\n",
            encoding="utf-8",
        )
        proc = run_cli(["--skill", str(unknown), "--snapshot", str(SCAN_OK)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("未知字段 dependencies.tools.extra", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def _ok_text(self) -> str:
        return (
            "---\nname: ok\ndependencies:\n  tools:\n    all:\n      - search\n"
            "requires-mcp-servers:\n  - docs\n---\n\nBODY_MARKER_DO_NOT_EXECUTE\n"
        )

    def _ok_skill(self) -> Path:
        skill = Path(tempfile.mkdtemp(prefix="sdg-ok-")) / "ok"
        skill.mkdir()
        skill.joinpath("SKILL.md").write_text(self._ok_text(), encoding="utf-8")
        return skill


if __name__ == "__main__":
    unittest.main(verbosity=2)
