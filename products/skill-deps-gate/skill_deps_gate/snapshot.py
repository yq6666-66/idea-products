"""Validate the sample snapshot envelope. Native tools/list JSON is rejected."""

from __future__ import annotations

import json


class SnapshotError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


_EXAMPLE = (
    '{"skill_deps_gate_snapshot":1,"servers":[{"server":"docs","tools":[{"name":"search"}]}]}'
)
_NOT_ENVELOPE = (
    "快照不是样本封装；原生 tools/list 没有服务器身份，拒绝从工具名或前缀推测。"
    f"可用封装示例：{_EXAMPLE}"
)
_NO_IDENTITY = "快照缺少服务器身份，拒绝根据工具名推测服务器"


def load_snapshot(text: str) -> dict[str, set[str]]:
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except SnapshotError:
        raise
    except json.JSONDecodeError as exc:
        raise SnapshotError("快照不是合法 JSON") from exc
    if not isinstance(data, dict) or "skill_deps_gate_snapshot" not in data:
        raise SnapshotError(_NOT_ENVELOPE)
    if set(data) != {"skill_deps_gate_snapshot", "servers"}:
        raise SnapshotError("快照含不支持的字段")
    version = data["skill_deps_gate_snapshot"]
    if type(version) is not int or version != 1 or not isinstance(data["servers"], list):
        raise SnapshotError(_NOT_ENVELOPE)
    found: dict[str, set[str]] = {}
    for entry in data["servers"]:
        if not isinstance(entry, dict):
            raise SnapshotError("快照工具条目格式不正确")
        if set(entry) - {"server", "tools"}:
            raise SnapshotError("快照含不支持的字段")
        if "server" not in entry or not isinstance(entry["server"], str) or entry["server"] == "":
            raise SnapshotError(_NO_IDENTITY)
        tools = entry.get("tools")
        if not isinstance(tools, list):
            raise SnapshotError("快照工具条目格式不正确")
        names: set[str] = set()
        for tool in tools:
            if not isinstance(tool, dict) or set(tool) != {"name"}:
                raise SnapshotError("快照工具条目格式不正确")
            name = tool["name"]
            if not isinstance(name, str) or name == "":
                raise SnapshotError("快照工具条目格式不正确")
            names.add(name)
        found.setdefault(entry["server"], set()).update(names)
    return found


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    mapping: dict = {}
    for key, value in pairs:
        if key in mapping:
            raise SnapshotError("快照含重复键")
        mapping[key] = value
    return mapping
