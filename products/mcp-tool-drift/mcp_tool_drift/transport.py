from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request

from mcp_tool_drift.model import ServerSpec, redact

# Snapshot traffic is limited to the handshake and the tool catalogue.
ALLOWED_METHODS = frozenset({"initialize", "notifications/initialized", "tools/list"})
PROTOCOL_VERSION = "2024-11-05"


class TransportError(Exception):
    pass


class MethodRejected(TransportError):
    pass


def guard_method(method: str) -> None:
    if method not in ALLOWED_METHODS:
        raise MethodRejected(method)


class MockTransport:
    def __init__(self, tools_by_server: dict):
        self.tools_by_server = tools_by_server

    def list_tools(self, server: ServerSpec, timeout: float) -> list:
        for method in ("initialize", "notifications/initialized", "tools/list"):
            guard_method(method)
        try:
            tools = self.tools_by_server[server.name]
        except KeyError as exc:
            raise TransportError(f"no mock tools for {server.name}") from exc
        if not isinstance(tools, list):
            raise TransportError(f"mock tools for {server.name} must be a list")
        return tools


class HttpTransport:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.urlopen
        self._next_id = 0

    def list_tools(self, server: ServerSpec, timeout: float) -> list:
        if not server.url:
            raise TransportError(f"{server.name}: no url for http")
        self._post(
            server,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcp-tool-drift", "version": "0.1.0"},
            },
            timeout,
            expect_result=True,
        )
        self._post(server, "notifications/initialized", {}, timeout, expect_result=False)
        result = self._post(server, "tools/list", {}, timeout, expect_result=True)
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            raise TransportError("tools/list result missing tools")
        return tools

    def _post(self, server: ServerSpec, method: str, params: dict, timeout: float, expect_result: bool) -> dict:
        guard_method(method)
        if expect_result:
            self._next_id += 1
            message = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        else:
            message = {"jsonrpc": "2.0", "method": method, "params": params}
        request = urllib.request.Request(
            server.url or "",
            data=json.dumps(message).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                raw = response.read()
        except TimeoutError as exc:
            raise TimeoutError("timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise TimeoutError("timed out") from exc
            raise TransportError(f"http request failed: {exc}") from exc
        if not expect_result:
            return {}
        if not raw:
            raise TransportError(f"empty response for {method}")
        payload = json.loads(raw.decode())
        if not isinstance(payload, dict):
            raise TransportError(f"invalid response for {method}")
        if "error" in payload:
            raise TransportError(f"{method} failed")
        result = payload.get("result") or {}
        if not isinstance(result, dict):
            raise TransportError(f"invalid result for {method}")
        return result


def stdio_list_tools(server: ServerSpec, timeout: float) -> tuple[list, str]:
    """Spawn server.command. May execute that binary. Sends only the snapshot methods."""
    if not server.command:
        raise TransportError(f"{server.name}: no command for stdio")
    env = os.environ.copy()
    env.update(server.env)
    try:
        proc = subprocess.Popen(
            [server.command, *server.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
            bufsize=0,
        )
    except OSError as exc:
        raise TransportError(f"cannot start {server.command}: {exc}") from exc
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    stderr_box: list[bytes] = []

    def _drain() -> None:
        stderr_box.append(proc.stderr.read() if proc.stderr is not None else b"")

    drain = threading.Thread(target=_drain, daemon=True)
    drain.start()
    deadline = time.monotonic() + timeout
    tools: list = []
    try:
        tools = _exchange(proc, deadline)
        try:
            proc.stdin.close()
        except OSError:
            pass
        remaining = max(0.1, deadline - time.monotonic())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            _stop(proc)
    except TimeoutError as exc:
        raise TimeoutError("timed out") from exc
    finally:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except OSError:
            pass
        _stop(proc)
        drain.join(timeout=2)
    return tools, _stderr_text(stderr_box, server)


def _exchange(proc: subprocess.Popen, deadline: float) -> list:
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcp-tool-drift", "version": "0.1.0"},
            },
        },
    )
    _wait_result(proc, deadline, 1)
    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    result = _wait_result(proc, deadline, 2)
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise TransportError("tools/list result missing tools")
    return tools


def _send(proc: subprocess.Popen, message: dict) -> None:
    method = message.get("method")
    if isinstance(method, str):
        guard_method(method)
    assert proc.stdin is not None
    proc.stdin.write(_encode(message))
    proc.stdin.flush()


def _wait_result(proc: subprocess.Popen, deadline: float, request_id: int) -> dict:
    assert proc.stdin is not None and proc.stdout is not None
    while True:
        incoming = _read_frame(proc.stdout, deadline)
        if incoming.get("id") == request_id and "method" not in incoming:
            if "error" in incoming:
                raise TransportError(f"request {request_id} failed")
            result = incoming.get("result") or {}
            if not isinstance(result, dict):
                raise TransportError(f"invalid result for request {request_id}")
            return result
        if "method" in incoming and "id" in incoming:
            proc.stdin.write(
                _encode(
                    {
                        "jsonrpc": "2.0",
                        "id": incoming["id"],
                        "error": {"code": -32601, "message": "unsupported"},
                    }
                )
            )
            proc.stdin.flush()


def _encode(message: dict) -> bytes:
    body = json.dumps(message, separators=(",", ":")).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read_frame(stream, deadline: float) -> dict:
    header = b""
    while not header.endswith(b"\r\n\r\n"):
        header += _read_some(stream, deadline, 1)
        if len(header) > 8192:
            raise TransportError("header too large")
    length = None
    for line in header.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    if length is None:
        raise TransportError("missing Content-Length")
    if length < 0 or length > 8_000_000:
        raise TransportError("invalid Content-Length")
    body = _read_exact(stream, length, deadline)
    try:
        payload = json.loads(body.decode())
    except json.JSONDecodeError as exc:
        raise TransportError(f"invalid JSON frame: {exc}") from exc
    if not isinstance(payload, dict):
        raise TransportError("JSON frame must be an object")
    return payload


def _read_exact(stream, size: int, deadline: float) -> bytes:
    data = b""
    while len(data) < size:
        data += _read_some(stream, deadline, size - len(data))
    return data


def _read_some(stream, deadline: float, size: int) -> bytes:
    remain = deadline - time.monotonic()
    if remain <= 0:
        raise TimeoutError("timed out")
    ready, _, _ = select.select([stream], [], [], remain)
    if not ready:
        raise TimeoutError("timed out")
    chunk = os.read(stream.fileno(), size)
    if not chunk:
        raise TransportError("server closed stdout")
    return chunk


def _stderr_text(chunks: list[bytes], server: ServerSpec) -> str:
    text = b"".join(chunks).decode(errors="replace")
    return redact(text, server.env)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)
