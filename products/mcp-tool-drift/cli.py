#!/usr/bin/env python3
"""Read-only MCP tool drift. Not a health check.

Discover client configs, snapshot tools with initialize and tools/list, and
diff snapshots locally. stdio transport may spawn the configured command.
Does not invoke tools or rewrite configs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp_tool_drift.discover import discover_configs, parse_overrides
from mcp_tool_drift.model import format_server, parse_servers
from mcp_tool_drift.online import collect_snapshot
from mcp_tool_drift.snapshot import classify, dump_snapshot, tool_map
from mcp_tool_drift.transport import TransportError


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
        servers = parse_servers(config, "offline")
    except ValueError as exc:
        _die_unparseable(f"{args.config}: {exc}")
    for name in sorted(server.name for server in servers):
        print(name)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    try:
        overrides = parse_overrides(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    root = args.root if args.root is not None else Path.home()
    servers, warnings = discover_configs(root, overrides)
    for warning in warnings:
        print(warning, file=sys.stderr)
    for server in servers:
        print(format_server(server))
    return 0


def cmd_online(args: argparse.Namespace) -> int:
    if args.out is not None and args.out.resolve() == args.config.resolve():
        print("refusing to write snapshot over config", file=sys.stderr)
        return 2
    config = load_json(args.config)
    try:
        servers = parse_servers(config, args.client)
    except ValueError as exc:
        _die_unparseable(f"{args.config}: {exc}")
    if args.server:
        servers = [server for server in servers if server.name == args.server]
        if not servers:
            print(f"unknown server: {args.server}", file=sys.stderr)
            return 2
    mock_tools = None
    if args.transport == "mock":
        if args.mock_tools is None:
            print("mock transport requires --mock-tools", file=sys.stderr)
            return 2
        try:
            mock_tools = json.loads(args.mock_tools.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _die_unparseable(f"{args.mock_tools}: {exc}")
        if not isinstance(mock_tools, dict):
            _die_unparseable(f"{args.mock_tools}: expected a JSON object")
    try:
        snapshot, log = collect_snapshot(servers, args.transport, mock_tools, args.timeout)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except TransportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        _die_unparseable(str(exc))
    text = dump_snapshot(snapshot)
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8")
    if log:
        sys.stderr.write(log)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    try:
        before = tool_map(load_json(args.before))
        after = tool_map(load_json(args.after))
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
            "Read-only MCP tool drift. Not a health check. "
            "Discover client configs, snapshot tools with initialize and tools/list, "
            "and diff snapshots locally. "
            "stdio transport may spawn the configured command. "
            "Does not invoke tools or rewrite configs."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    offline = sub.add_parser("offline", help="parse one MCP config and list server names")
    offline.add_argument("--config", type=Path, required=True, help="Cursor-style mcp.json")
    offline.set_defaults(func=cmd_offline)

    discover = sub.add_parser("discover", help="read known client config paths and list servers")
    discover.add_argument(
        "--root",
        type=Path,
        default=None,
        help="directory used as home for default path patterns (default: your home directory)",
    )
    discover.add_argument(
        "--path",
        action="append",
        default=[],
        metavar="CLIENT=FILE",
        help="replace default paths for a client (repeatable). Unknown or bad files are skipped with a warning",
    )
    discover.set_defaults(func=cmd_discover)

    online = sub.add_parser(
        "online",
        help="snapshot tools via initialize and tools/list (stdio may spawn the configured command)",
    )
    online.add_argument("--config", type=Path, required=True, help="one MCP config file")
    online.add_argument("--client", default="cursor", help="client label stored with the parsed servers")
    online.add_argument("--transport", choices=("mock", "stdio", "http"), help="default: stdio if command is set, otherwise http")
    online.add_argument("--mock-tools", type=Path, help="server name → tool list, used when --transport mock")
    online.add_argument("--timeout", type=float, default=10.0, help="seconds for each server exchange")
    online.add_argument("--server", help="snapshot only this server name")
    online.add_argument("--out", type=Path, help="write the snapshot here instead of stdout")
    online.set_defaults(func=cmd_online)

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
