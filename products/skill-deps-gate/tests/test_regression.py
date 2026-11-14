"""Regression for all, any, binding, inputs, and read-only behavior."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


def write_skill(folder: Path, frontmatter: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath("SKILL.md").write_text(
        f"---\n{frontmatter}---\n\nBODY_MARKER_DO_NOT_EXECUTE\n",
        encoding="utf-8",
    )


def snapshot(payload: str) -> Path:
    directory = Path(tempfile.mkdtemp(prefix="sdg-snap-"))
    path = directory / "snapshot.json"
    path.write_text(payload, encoding="utf-8")
    return path


def matrix(stdout: str) -> list[list[str]]:
    lines = stdout.splitlines()
    assert lines and lines[0] == HEADER, stdout
    return [line.split("\t") for line in lines[1:]]


DOCS_BOTH = """{
  "skill_deps_gate_snapshot": 1,
  "servers": [
    {"server": "docs", "tools": [{"name": "search"}, {"name": "fetch"}]},
    {"server": "other", "tools": [{"name": "othertool"}]}
  ]
}
"""


class RegressionTests(unittest.TestCase):
    def test_all_and_any_both_need_to_pass(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-both-"))
        write_skill(
            base / "both",
            "name: both\ndependencies:\n  tools:\n    all:\n      - search\n    any:\n      - fetch\n      - missingany\nrequires-mcp-servers:\n  - docs\n",
        )
        proc = run_cli(["--skill", str(base / "both"), "--snapshot", str(snapshot(DOCS_BOTH))])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = matrix(proc.stdout)
        self.assertIn("满足", proc.stdout)
        self.assertEqual([row[2] for row in rows if row[3] == "tools.all"], ["search"])
        self.assertEqual(rows[0][4], "满足")

    def test_satisfied_any_does_not_cover_missing_all(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-cover-"))
        write_skill(
            base / "cover",
            "name: cover\ndependencies:\n  tools:\n    all:\n      - absenttool\n    any:\n      - search\nrequires-mcp-servers:\n  - docs\n",
        )
        proc = run_cli(["--skill", str(base / "cover"), "--snapshot", str(snapshot(DOCS_BOTH))])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("unsatisfied: absenttool", proc.stderr)
        self.assertNotIn("dependencies.tools.any", proc.stderr)

    def test_satisfied_all_does_not_cover_missing_any(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-any-miss-"))
        write_skill(
            base / "anymiss",
            "name: anymiss\ndependencies:\n  tools:\n    all:\n      - search\n    any:\n      - nothere\nrequires-mcp-servers:\n  - docs\n",
        )
        proc = run_cli(["--skill", str(base / "anymiss"), "--snapshot", str(snapshot(DOCS_BOTH))])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stderr, "unsatisfied: dependencies.tools.any\n")

    def test_any_without_servers_uses_global_tool_set(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-global-"))
        write_skill(
            base / "global",
            "name: global-any\ndependencies:\n  tools:\n    any:\n      - othertool\n",
        )
        proc = run_cli(["--skill", str(base / "global"), "--snapshot", str(snapshot(DOCS_BOTH))])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(matrix(proc.stdout)[0][4], "满足")

    def test_multiple_servers_with_tools_are_rejected(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-multi-"))
        write_skill(
            base / "multi",
            "name: multi\ndependencies:\n  tools:\n    any:\n      - search\nrequires-mcp-servers:\n  - docs\n  - other\n",
        )
        proc = run_cli(["--skill", str(base / "multi"), "--snapshot", str(snapshot(DOCS_BOTH))])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("拒绝猜成交叉积", proc.stderr)
        self.assertNotIn("满足", proc.stdout)

    def test_native_tools_list_includes_envelope_example(self) -> None:
        proc = run_cli(
            ["--skill", "fixtures/skill-any", "--snapshot", "fixtures/snapshots/native-tools-list.json"]
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("原生 tools/list 没有服务器身份", proc.stderr)
        self.assertIn("可用封装示例", proc.stderr)
        self.assertIn('"skill_deps_gate_snapshot":1', proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_prefix_is_not_a_tool_match(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-prefix-"))
        write_skill(
            base / "prefix",
            "name: prefix\ndependencies:\n  tools:\n    all:\n      - search\nrequires-mcp-servers:\n  - docs\n",
        )
        payload = """{
          "skill_deps_gate_snapshot": 1,
          "servers": [{"server": "docs", "tools": [{"name": "searching"}]}]
        }
        """
        proc = run_cli(["--skill", str(base / "prefix"), "--snapshot", str(snapshot(payload))])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(matrix(proc.stdout)[0][4], "缺失")

    def test_non_utf8_and_oversize_do_not_crash_or_pass(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-bytes-"))
        skill = base / "bad"
        skill.mkdir()
        skill.joinpath("SKILL.md").write_bytes(b"\xff\xfe not utf8")
        proc = run_cli(["--skill", str(skill), "--snapshot", "fixtures/snapshots/scan-ok.json"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("不是 UTF-8", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        huge = base / "huge"
        huge.mkdir()
        huge.joinpath("SKILL.md").write_bytes(b"-" * (1024 * 1024 + 1))
        proc = run_cli(["--skill", str(huge), "--snapshot", "fixtures/snapshots/scan-ok.json"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("过大", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_bad_frontmatter_is_not_covered_by_another_pass(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-bad-mix-"))
        write_skill(
            base / "ok",
            "name: ok\ndependencies:\n  tools:\n    all:\n      - search\nrequires-mcp-servers:\n  - docs\n",
        )
        (base / "broken").mkdir()
        (base / "broken" / "SKILL.md").write_text("---\nname: broken\n", encoding="utf-8")
        proc = run_cli(["--skill", str(base), "--snapshot", "fixtures/snapshots/scan-ok.json"])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("frontmatter 解析失败", proc.stderr)
        self.assertNotIn("满足", proc.stdout)
        self.assertIn("未判定", proc.stdout)

    def test_fixtures_stay_unchanged_and_body_is_not_executed(self) -> None:
        before = {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "fixtures").rglob("*"))
            if path.is_file()
        }
        proc = run_cli(["--skill", "fixtures/skill-any", "--snapshot", "fixtures/snapshots/any-on-docs.json"])
        after = {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "fixtures").rglob("*"))
            if path.is_file()
        }
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(before, after)
        self.assertIn("BODY_MARKER_DO_NOT_EXECUTE", (ROOT / "fixtures" / "skill-any" / "SKILL.md").read_text())
        self.assertFalse((ROOT / "fixtures" / "skill-any" / "SHOULD_NOT_EXIST").exists())

    def test_illegal_json_exits_2(self) -> None:
        path = snapshot("{")
        proc = run_cli(["--skill", "fixtures/skill-any", "--snapshot", str(path)])
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("快照不是合法 JSON", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_matcher_does_not_parse_declaration_field_names(self) -> None:
        match_text = (ROOT / "skill_deps_gate" / "match.py").read_text(encoding="utf-8")
        adapt_text = (ROOT / "skill_deps_gate" / "adapt.py").read_text(encoding="utf-8")
        self.assertNotIn("requires-mcp-servers", match_text)
        self.assertNotIn("dependencies", match_text)
        self.assertIn("requires-mcp-servers", adapt_text)
        self.assertIn('"any"', adapt_text)

    def test_no_declaration_does_not_pass(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="sdg-nodeps-"))
        write_skill(base / "plain", "name: plain\ndescription: none\n")
        proc = run_cli(["--skill", str(base / "plain"), "--snapshot", "fixtures/snapshots/scan-ok.json"])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("拒绝视为通过", proc.stderr)
        self.assertNotIn("\t满足", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
