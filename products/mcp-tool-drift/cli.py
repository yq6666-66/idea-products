#!/usr/bin/env python3
"""Read-only MCP tool-drift samples. Not a health check.

Lists server names from a client config, or diffs two local tool snapshots.
Does not spawn servers and does not call tools.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _die_unparseable(detail: str) -> None:
    print(f"unparseable JSON: {detail}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _die_unparseable(f"{path}: {exc}")
    if not isinstance(data, dict):
        _die_unparseable(f"{path}: expected a JSON object")
    return data


def server_names(config: dict) -> list[str]:
    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object")
    names: list[str] = []
    for name, spec in servers.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ValueError(f"invalid server entry: {name!r}")
        names.append(name)
    return sorted(names)


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


def classify(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], list[str], list[str], list[str]]:
    before_names = set(before)
    after_names = set(after)
    added = sorted(after_names - before_names)
    removed = sorted(before_names - after_names)
    breaking = sorted(name for name in before_names & after_names if before[name] != after[name])
    unchanged = sorted(name for name in before_names & after_names if before[name] == after[name])
    return added, removed, breaking, unchanged


def print_section(title: str, names: list[str]) -> None:
    print(f"{title}:")
    if not names:
        print("  (none)")
        return
    for name in names:
        print(f"  {name}")


def cmd_offline(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    try:
        names = server_names(config)
    except ValueError as exc:
        _die_unparseable(f"{args.config}: {exc}")
    for name in names:
        print(name)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    try:
        before = schema_hashes(load_json(args.before))
        after = schema_hashes(load_json(args.after))
    except ValueError as exc:
        _die_unparseable(str(exc))
    added, removed, breaking, unchanged = classify(before, after)
    print_section("added", added)
    print_section("removed", removed)
    print_section("breaking", breaking)
    print_section("unchanged", unchanged)
    if args.warn_only:
        return 0
    if removed or breaking:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MCP tool drift samples: list servers from a config, "
            "or diff two tool snapshots. Not a health check. "
            "Does not spawn servers or call tools."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    offline = sub.add_parser("offline", help="parse a client MCP config and list server names")
    offline.add_argument("--config", type=Path, required=True, help="Cursor-style mcp.json")
    offline.set_defaults(func=cmd_offline)

    diff = sub.add_parser("diff", help="diff two local tool snapshots")
    diff.add_argument("--before", type=Path, required=True, help="earlier snapshot JSON")
    diff.add_argument("--after", type=Path, required=True, help="later snapshot JSON")
    diff.add_argument(
        "--warn-only",
        action="store_true",
        help="exit 0 even when tools were removed or schema hashes changed",
    )
    diff.set_defaults(func=cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
