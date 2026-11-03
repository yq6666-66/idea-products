from __future__ import annotations

import json
from pathlib import Path

from mcp_tool_drift.model import ServerSpec, parse_servers

# First existing default path wins for each client. Overrides replace this list.
DEFAULT_PATTERNS: dict[str, tuple[str, ...]] = {
    "cursor": (".cursor/mcp.json",),
    "claude-desktop": (
        "Library/Application Support/Claude/claude_desktop_config.json",
        ".config/Claude/claude_desktop_config.json",
        "AppData/Roaming/Claude/claude_desktop_config.json",
    ),
}


def parse_overrides(items: list[str]) -> dict[str, list[Path]]:
    overrides: dict[str, list[Path]] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"path override must be CLIENT=FILE: {item}")
        client, raw = item.split("=", 1)
        client = client.strip()
        if client not in DEFAULT_PATTERNS:
            raise ValueError(f"unknown client: {client}")
        if not raw:
            raise ValueError(f"path override must be CLIENT=FILE: {item}")
        overrides.setdefault(client, []).append(Path(raw))
    return overrides


def discover_configs(root: Path, overrides: dict[str, list[Path]]) -> tuple[list[ServerSpec], list[str]]:
    """Read configs. Missing or unrecognized files are skipped with a warning."""
    found: list[ServerSpec] = []
    warnings: list[str] = []
    for client in DEFAULT_PATTERNS:
        explicit = client in overrides
        paths = overrides[client] if explicit else [root / rel for rel in DEFAULT_PATTERNS[client]]
        for path in paths:
            if not path.is_file():
                if explicit:
                    warnings.append(f"warn: skip missing {path}")
                continue
            loaded = _load_file(path, client)
            if isinstance(loaded, str):
                warnings.append(loaded)
                continue
            found.extend(loaded)
            if not explicit:
                break
    found.sort(key=lambda server: (server.client, server.name))
    return found, warnings


def _load_file(path: Path, client: str) -> list[ServerSpec] | str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"warn: skip unparseable {path}: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers"), dict):
        return f"warn: skip unknown {path}: no mcpServers object"
    try:
        return parse_servers(data, client)
    except ValueError as exc:
        return f"warn: skip unparseable {path}: {exc}"
