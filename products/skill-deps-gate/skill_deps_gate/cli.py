"""Read-only CLI. It prints a skill-by-dependency matrix and does not write inputs."""

from __future__ import annotations

import sys
from pathlib import Path

from skill_deps_gate.adapt import Adapted, DeclarationError, Refusal, adapt
from skill_deps_gate.frontmatter import FrontmatterError, read_frontmatter
from skill_deps_gate.match import match
from skill_deps_gate.scan import FoundSkill, discover
from skill_deps_gate.snapshot import SnapshotError, load_snapshot

_MAX_BYTES = 1_000_000
_HEADER = "技能\t路径\t依赖\t种类\t状态"


class InputError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(sys.argv[1:] if argv is None else argv)
    except (FrontmatterError, DeclarationError, SnapshotError, InputError) as exc:
        sys.stderr.write(f"error: {exc.message}\n")
        return 2
    except Exception:
        sys.stderr.write("error: 未能完成检查\n")
        return 2


def _run(argv: list[str]) -> int:
    roots, snapshot_arg = _parse_args(argv)
    snapshot_file = _snapshot_file(snapshot_arg)
    servers = load_snapshot(_read_text(snapshot_file, "快照"))
    found, scan_errors = discover(roots)
    evaluations = [_evaluate(skill, servers) for skill in found]
    multiple = len(evaluations) + len(scan_errors) > 1
    blocked = bool(scan_errors) or any(item.code == 2 for item in evaluations)
    rows = []
    messages: list[str] = []
    for message in scan_errors:
        messages.append(f"error: {message}")
    for item in evaluations:
        rows.extend(_block(item.rows, blocked))
        if item.message:
            messages.append(_scope(item.display, item.message, multiple))
    if rows:
        _write_matrix(rows)
    for message in messages:
        sys.stderr.write(message + "\n")
    if blocked:
        return 2
    if any(item.code == 1 for item in evaluations):
        return 1
    if not evaluations:
        return 2
    return 0


class _Evaluation:
    def __init__(self, display: str, rows: list[tuple[str, str, str, str, str]], message: str, code: int) -> None:
        self.display = display
        self.rows = rows
        self.message = message
        self.code = code


def _evaluate(skill: FoundSkill, servers: dict[str, set[str]]) -> _Evaluation:
    try:
        text = _read_text(skill.skill_md, "SKILL.md")
        adapted = adapt(read_frontmatter(text), skill.directory_name)
    except (FrontmatterError, DeclarationError, InputError) as exc:
        row = (skill.directory_name, skill.display, "(错误)", "输入", "错误")
        return _Evaluation(skill.display, [row], f"error: {exc.message}", 2)
    if isinstance(adapted, Refusal):
        return _Evaluation(skill.display, _locate(skill.display, adapted.rows), adapted.stderr, 1)
    if not isinstance(adapted, Adapted):
        row = (skill.directory_name, skill.display, "(错误)", "输入", "错误")
        return _Evaluation(skill.display, [row], "error: 依赖声明格式不正确", 2)
    matched = match(adapted.skill, adapted.needs, servers, adapted.bound_server)
    located = _locate(skill.display, matched)
    parts = _failure_parts(located)
    if parts:
        return _Evaluation(skill.display, located, "unsatisfied: " + ", ".join(parts), 1)
    return _Evaluation(skill.display, located, "", 0)


def _failure_parts(rows: list[tuple[str, str, str, str, str]]) -> list[str]:
    any_rows = [row for row in rows if row[3] == "tools.any"]
    parts: list[str] = []
    if any_rows and not any(row[4] == "满足" for row in any_rows):
        parts.append("dependencies.tools.any")
    for row in rows:
        if row[4] == "缺失" and row[3] != "tools.any":
            parts.append(row[2])
    return parts


def _locate(display: str, rows: list[tuple[str, str, str, str]] | tuple[tuple[str, str, str, str], ...]) -> list[tuple[str, str, str, str, str]]:
    return [(row[0], display, row[1], row[2], row[3]) for row in rows]


def _block(rows: list[tuple[str, str, str, str, str]], blocked: bool) -> list[tuple[str, str, str, str, str]]:
    if not blocked:
        return rows
    blocked_rows = []
    for row in rows:
        status = "未判定" if row[4] == "满足" else row[4]
        blocked_rows.append((row[0], row[1], row[2], row[3], status))
    return blocked_rows


def _scope(display: str, message: str, multiple: bool) -> str:
    if not multiple or message.startswith("error:"):
        if message.startswith("error:") and multiple:
            return f"error: {display}: {message[len('error: '):]}"
        return message
    kind, _, rest = message.partition(": ")
    return f"{kind}: {display}: {rest}"


def _parse_args(argv: list[str]) -> tuple[list[str], str]:
    roots: list[str] = []
    snapshot = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--skill":
            roots.append(_take_value(argv, index, "--skill"))
            index += 2
            continue
        if arg == "--snapshot":
            if snapshot is not None:
                raise InputError("参数重复: --snapshot")
            snapshot = _take_value(argv, index, "--snapshot")
            index += 2
            continue
        raise InputError(f"不支持的参数: {arg}")
    if not roots:
        raise InputError("缺少参数 --skill")
    if snapshot is None:
        raise InputError("缺少参数 --snapshot")
    return roots, snapshot


def _take_value(argv: list[str], index: int, flag: str) -> str:
    if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
        raise InputError(f"缺少参数 {flag}")
    return argv[index + 1]


def _snapshot_file(raw: str) -> Path:
    path = Path(raw)
    try:
        exists = path.exists()
        is_file = path.is_file()
    except OSError as exc:
        raise InputError("快照不可读") from exc
    if not exists:
        raise InputError("找不到快照文件")
    if path.is_symlink():
        raise InputError("快照路径不允许符号链接")
    if not is_file:
        raise InputError("快照路径不是文件")
    return path


def _read_text(path: Path, kind: str) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InputError(f"{kind}不可读") from exc
    if len(data) > _MAX_BYTES:
        raise InputError(f"{kind}过大")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{kind}不是 UTF-8") from exc


def _write_matrix(rows: list[tuple[str, str, str, str, str]]) -> None:
    lines = [_HEADER]
    lines.extend("\t".join(row) for row in rows)
    sys.stdout.write("\n".join(lines) + "\n")
