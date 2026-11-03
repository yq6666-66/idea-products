#!/usr/bin/env python3
"""Local stdio stand-in for the demo. Not a real MCP server and not on the network.

Answers the snapshot handshake, then exits when stdin closes.
"""
from __future__ import annotations

import json
import sys

TOOLS = [
    {
        "name": "echo",
        "description": "echo text",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
    }
]


def read_message() -> dict | None:
    header = b""
    while not header.endswith(b"\r\n\r\n"):
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
        if len(header) > 8192:
            return None
    length = None
    for line in header.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    if length is None:
        return None
    body = sys.stdin.buffer.read(length)
    if len(body) < length:
        return None
    return json.loads(body.decode())


def write_message(payload: dict) -> None:
    body = json.dumps(payload).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


def main() -> int:
    while True:
        message = read_message()
        if message is None:
            return 0
        method = message.get("method")
        if isinstance(method, str):
            print(f"method {method}", file=sys.stderr, flush=True)
        if method == "initialize":
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake", "version": "0"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            write_message({"jsonrpc": "2.0", "id": message.get("id"), "result": {"tools": TOOLS}})
        elif "id" in message and isinstance(method, str):
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": "unsupported"},
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
