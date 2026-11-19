"""Single-server any binding. These two cases are the first RED."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "fixtures" / "skill-any"
ON_DOCS = ROOT / "fixtures" / "snapshots" / "any-on-docs.json"
ON_OTHER = ROOT / "fixtures" / "snapshots" / "any-on-other.json"
HEADER = "技能\t路径\t依赖\t种类\t状态"
SKILL_ARG = "fixtures/skill-any"


def run_cli(snapshot: Path) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_deps_gate",
            "--skill",
            SKILL_ARG,
            "--snapshot",
            str(snapshot),
        ],
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


class AnyBindingTests(unittest.TestCase):
    def test_any_passes_when_one_tool_is_on_named_server(self) -> None:
        proc = run_cli(ON_DOCS)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(
            matrix(proc.stdout),
            [
                ["fixture-any", SKILL_ARG, "search", "tools.any", "满足"],
                ["fixture-any", SKILL_ARG, "fetch", "tools.any", "缺失"],
                ["fixture-any", SKILL_ARG, "docs", "requires-mcp-servers", "满足"],
            ],
        )
        self.assertFalse((SKILL / "SHOULD_NOT_EXIST").exists())

    def test_any_fails_when_tools_exist_only_on_another_server(self) -> None:
        proc = run_cli(ON_OTHER)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(
            matrix(proc.stdout),
            [
                ["fixture-any", SKILL_ARG, "search", "tools.any", "缺失"],
                ["fixture-any", SKILL_ARG, "fetch", "tools.any", "缺失"],
                ["fixture-any", SKILL_ARG, "docs", "requires-mcp-servers", "满足"],
            ],
        )
        self.assertEqual(proc.stderr, "unsatisfied: dependencies.tools.any\n")
        self.assertFalse((SKILL / "SHOULD_NOT_EXIST").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
