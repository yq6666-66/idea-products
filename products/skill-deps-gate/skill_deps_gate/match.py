"""Exact membership checks. This module does not interpret declaration field names."""

from __future__ import annotations

from skill_deps_gate.adapt import Need


def match(
    skill: str,
    needs: tuple[Need, ...],
    servers: dict[str, set[str]],
    bound_server: str | None = None,
) -> list[tuple[str, str, str, str]]:
    if bound_server is None:
        tool_names: set[str] = set()
        for names in servers.values():
            tool_names.update(names)
    else:
        tool_names = set(servers.get(bound_server, set()))
    server_ids = set(servers)
    rows: list[tuple[str, str, str, str]] = []
    for need in needs:
        if need.group == "any-empty":
            rows.append((skill, need.dependency, need.kind_label, "缺失"))
            continue
        if need.group == "any":
            status = "满足" if need.dependency in tool_names else "缺失"
            rows.append((skill, need.dependency, need.kind_label, status))
            continue
        universe = tool_names if need.pool == "tool" else server_ids
        status = "满足" if need.dependency in universe else "缺失"
        rows.append((skill, need.dependency, need.kind_label, status))
    return rows
