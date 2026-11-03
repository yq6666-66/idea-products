from __future__ import annotations

import hashlib
import json


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def schema_hash(schema: object) -> str:
    return hashlib.sha256(canonical(schema).encode()).hexdigest()


def description_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def snapshot_from_tools(tools: list[dict]) -> dict[str, dict[str, str]]:
    snapshot: dict[str, dict[str, str]] = {}
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"]:
            raise ValueError("tool entry missing name")
        name = tool["name"]
        schema = tool.get("inputSchema")
        if schema is None:
            schema = {}
        if not isinstance(schema, (dict, list)):
            raise ValueError(f"inputSchema must be a JSON object or array for {name}")
        record = {"schema_hash": schema_hash(schema)}
        description = tool.get("description")
        if isinstance(description, str):
            record["description_hash"] = description_hash(description)
        snapshot[name] = record
    return snapshot


def is_server_envelope(snapshot: dict) -> bool:
    if set(snapshot) != {"servers"}:
        return False
    servers = snapshot.get("servers")
    if not isinstance(servers, dict):
        return False
    for value in servers.values():
        if not isinstance(value, dict) or "schema_hash" in value:
            return False
    return True


def schema_hashes(snapshot: dict) -> dict[str, str]:
    tools: dict[str, str] = {}
    for name, spec in snapshot.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ValueError(f"invalid tool entry: {name!r}")
        schema = spec.get("schema_hash")
        if not isinstance(schema, str) or not schema:
            raise ValueError(f"missing schema_hash for {name}")
        tools[name] = schema
    return tools


def tool_map(snapshot: dict) -> dict[str, str]:
    """Flat tool → schema hash. Multi-server files use server/tool names."""
    if is_server_envelope(snapshot):
        flat: dict[str, str] = {}
        for server, tools in snapshot["servers"].items():
            if not isinstance(server, str) or not server or not isinstance(tools, dict):
                raise ValueError("invalid servers envelope")
            for tool, digest in schema_hashes(tools).items():
                flat[f"{server}/{tool}"] = digest
        return flat
    return schema_hashes(snapshot)


def classify(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], list[str], list[str], list[str]]:
    before_names = set(before)
    after_names = set(after)
    added = sorted(after_names - before_names)
    removed = sorted(before_names - after_names)
    shared = before_names & after_names
    breaking = sorted(name for name in shared if before[name] != after[name])
    unchanged = sorted(name for name in shared if before[name] == after[name])
    return added, removed, breaking, unchanged


def dump_snapshot(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
