from __future__ import annotations

from mcp_tool_drift.model import ServerSpec
from mcp_tool_drift.snapshot import snapshot_from_tools
from mcp_tool_drift.transport import HttpTransport, MockTransport, TransportError, stdio_list_tools


def choose_transport(server: ServerSpec, forced: str | None) -> str:
    if forced:
        return forced
    if server.command:
        return "stdio"
    if server.url:
        return "http"
    raise TransportError(f"{server.name}: no command or url")


def collect_snapshot(
    servers: list[ServerSpec],
    forced: str | None,
    mock_tools: dict | None,
    timeout: float,
) -> tuple[dict, str]:
    """Return a snapshot document and any redacted server stderr."""
    logs: list[str] = []
    per_server: dict[str, dict] = {}
    mock = MockTransport(mock_tools or {})
    http = HttpTransport()
    for server in servers:
        kind = choose_transport(server, forced)
        if kind == "mock":
            tools = mock.list_tools(server, timeout)
            err = ""
        elif kind == "stdio":
            tools, err = stdio_list_tools(server, timeout)
        elif kind == "http":
            tools = http.list_tools(server, timeout)
            err = ""
        else:
            raise TransportError(f"unknown transport {kind}")
        if err:
            logs.append(err if err.endswith("\n") else err + "\n")
        per_server[server.name] = snapshot_from_tools(tools)
    if len(per_server) == 1:
        return next(iter(per_server.values())), "".join(logs)
    return {"servers": per_server}, "".join(logs)
