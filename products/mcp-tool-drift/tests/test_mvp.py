from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli.py"
DEMO = ROOT / "demo"
BANNED_METHOD = "tools/" + "call"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _schema_hash(schema: object) -> str:
    return hashlib.sha256(_canonical(schema).encode()).hexdigest()


def _write_config(path: Path, servers: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n", encoding="utf-8")


def test_discover_cursor_and_claude_masks_env_and_does_not_write(tmp_path: Path):
    secret = "super-secret-value"
    cursor = tmp_path / ".cursor" / "mcp.json"
    claude = tmp_path / ".config" / "Claude" / "claude_desktop_config.json"
    _write_config(
        cursor,
        {
            "demo-fs": {
                "command": "npx",
                "args": ["-y", "@example/mcp-fs"],
                "env": {"DEMO_TOKEN": secret},
            }
        },
    )
    _write_config(
        claude,
        {"demo-notes": {"command": "uvx", "args": ["example-mcp-notes"], "env": {"API_KEY": secret}}},
    )
    before = {cursor: cursor.read_bytes(), claude: claude.read_bytes()}
    r = _run(["discover", "--root", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    assert "cursor\tdemo-fs\tcommand=npx\targs=-y @example/mcp-fs\turl=-\tenv=DEMO_TOKEN=***" in r.stdout
    assert "claude-desktop\tdemo-notes\tcommand=uvx\targs=example-mcp-notes\turl=-\tenv=API_KEY=***" in r.stdout
    assert secret not in r.stdout
    assert secret not in r.stderr
    assert cursor.read_bytes() == before[cursor]
    assert claude.read_bytes() == before[claude]


def test_discover_path_override_and_warn_skip(tmp_path: Path):
    secret = "override-secret"
    custom = tmp_path / "custom-cursor.json"
    _write_config(custom, {"only-custom": {"url": "http://127.0.0.1:9/mcp", "env": {"TOKEN": secret}}})
    missing = tmp_path / "missing.json"
    unknown = tmp_path / "unknown.json"
    unknown.write_text("{}\n", encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    empty_home = tmp_path / "home"
    empty_home.mkdir()
    r = _run(
        [
            "discover",
            "--root",
            str(empty_home),
            "--path",
            f"cursor={custom}",
            "--path",
            f"claude-desktop={missing}",
            "--path",
            f"cursor={unknown}",
            "--path",
            f"cursor={bad}",
        ]
    )
    assert r.returncode == 0, r.stderr
    assert "cursor\tonly-custom\tcommand=-\targs=\turl=http://127.0.0.1:9/mcp\tenv=TOKEN=***" in r.stdout
    assert secret not in r.stdout + r.stderr
    assert "warn:" in r.stderr
    assert "missing" in r.stderr
    assert "unknown" in r.stderr
    assert "bad.json" in r.stderr
    assert custom.read_text(encoding="utf-8").count(secret) == 1


def test_discover_unknown_client_exits_2(tmp_path: Path):
    r = _run(["discover", "--root", str(tmp_path), "--path", "nope=/tmp/x.json"])
    assert r.returncode == 2
    assert "unknown client" in r.stderr


def test_discover_mac_claude_pattern(tmp_path: Path):
    mac = tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    _write_config(mac, {"mac-notes": {"command": "notes-mcp"}})
    r = _run(["discover", "--root", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    assert "claude-desktop\tmac-notes\tcommand=notes-mcp\t" in r.stdout


def test_online_mock_hashes_schema_and_never_spawns(tmp_path: Path):
    schema = {"type": "object", "properties": {"b": {"type": "string"}, "a": {"type": "number"}}}
    reordered = {"properties": {"a": {"type": "number"}, "b": {"type": "string"}}, "type": "object"}
    config = tmp_path / "mcp.json"
    _write_config(
        config,
        {"demo-fs": {"command": "this-binary-must-not-exist", "env": {"DEMO_TOKEN": "super-secret-value"}}},
    )
    tools = tmp_path / "tools.json"
    tools.write_text(
        json.dumps(
            {
                "demo-fs": [
                    {"name": "list_dir", "description": "list", "inputSchema": schema},
                    {"name": "ping", "inputSchema": reordered},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "snap.json"
    before = config.read_bytes()
    r = _run(
        [
            "online",
            "--config",
            str(config),
            "--transport",
            "mock",
            "--mock-tools",
            str(tools),
            "--timeout",
            "2",
            "--out",
            str(out),
        ]
    )
    assert r.returncode == 0, r.stderr
    assert "super-secret-value" not in r.stdout + r.stderr
    assert config.read_bytes() == before
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["list_dir"]["schema_hash"] == _schema_hash(schema)
    assert snap["list_dir"]["description_hash"] == hashlib.sha256(b"list").hexdigest()
    assert snap["ping"]["schema_hash"] == _schema_hash(schema)
    assert "description_hash" not in snap["ping"]
    assert BANNED_METHOD not in r.stdout + r.stderr


def test_online_multi_server_envelope_and_diff(tmp_path: Path):
    config = tmp_path / "mcp.json"
    _write_config(
        config,
        {
            "alpha": {"command": "alpha"},
            "beta": {"url": "http://127.0.0.1:9/mcp"},
        },
    )
    before_tools = {
        "alpha": [{"name": "keep", "inputSchema": {"type": "object"}}],
        "beta": [
            {"name": "gone", "inputSchema": {"type": "object"}},
            {"name": "shift", "inputSchema": {"type": "object", "properties": {"n": {"type": "string"}}}},
        ],
    }
    after_tools = {
        "alpha": [
            {"name": "keep", "inputSchema": {"type": "object"}},
            {"name": "fresh", "inputSchema": {"type": "object"}},
        ],
        "beta": [{"name": "shift", "inputSchema": {"type": "object", "properties": {"n": {"type": "number"}}}}],
    }
    before_path = tmp_path / "before-tools.json"
    after_path = tmp_path / "after-tools.json"
    before_path.write_text(json.dumps(before_tools), encoding="utf-8")
    after_path.write_text(json.dumps(after_tools), encoding="utf-8")
    before_snap = tmp_path / "before.json"
    after_snap = tmp_path / "after.json"
    r1 = _run(
        ["online", "--config", str(config), "--transport", "mock", "--mock-tools", str(before_path), "--out", str(before_snap)]
    )
    r2 = _run(
        ["online", "--config", str(config), "--transport", "mock", "--mock-tools", str(after_path), "--out", str(after_snap)]
    )
    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr
    envelope = json.loads(before_snap.read_text(encoding="utf-8"))
    assert set(envelope) == {"servers"}
    diff = _run(["diff", "--before", str(before_snap), "--after", str(after_snap)])
    assert diff.returncode == 1, diff.stderr
    assert "added:\n  alpha/fresh\n" in diff.stdout
    assert "removed:\n  beta/gone\n" in diff.stdout
    assert "breaking:\n  beta/shift\n" in diff.stdout
    assert "unchanged:\n  alpha/keep\n" in diff.stdout
    warned = _run(["diff", "--before", str(before_snap), "--after", str(after_snap), "--warn-only"])
    assert warned.returncode == 0, warned.stderr
    assert warned.stdout == diff.stdout


def test_online_stdio_fake_lists_tools_and_rejects_tool_invocation(tmp_path: Path):
    secret = "stdio-secret-value"
    config = tmp_path / "mcp.json"
    _write_config(
        config,
        {
            "fake": {
                "command": sys.executable,
                "args": [str(DEMO / "fake_mcp.py")],
                "env": {"DEMO_TOKEN": secret},
            }
        },
    )
    out = tmp_path / "snap.json"
    r = _run(
        [
            "online",
            "--config",
            str(config),
            "--transport",
            "stdio",
            "--timeout",
            "5",
            "--out",
            str(out),
        ]
    )
    assert r.returncode == 0, r.stderr
    assert secret not in r.stdout + r.stderr
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert "echo" in snap
    assert snap["echo"]["schema_hash"] == _schema_hash(
        {"type": "object", "properties": {"text": {"type": "string"}}, "additionalProperties": False}
    )
    methods = [line.split()[1] for line in r.stderr.splitlines() if line.startswith("method ")]
    assert methods == ["initialize", "notifications/initialized", "tools/list"]
    assert BANNED_METHOD not in methods


def test_online_stdio_timeout(tmp_path: Path):
    config = tmp_path / "mcp.json"
    _write_config(
        config,
        {"slow": {"command": sys.executable, "args": ["-c", "import time; time.sleep(30)"]}},
    )
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "online",
            "--config",
            str(config),
            "--transport",
            "stdio",
            "--timeout",
            "0.4",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=8,
    )
    assert r.returncode == 2
    assert "timeout" in r.stderr.lower() or "timed out" in r.stderr.lower()


def test_online_bad_config_exits_2():
    r = _run(["online", "--config", str(DEMO / "cursor-mcp.bad.json"), "--transport", "mock", "--mock-tools", str(DEMO / "mock-tools.json")])
    assert r.returncode == 2
    assert "JSON" in r.stderr or "json" in r.stderr


def test_library_does_not_name_tool_invocation_method():
    package = ROOT / "mcp_tool_drift"
    assert package.is_dir()
    roots = [package, CLI]
    for path in roots:
        files = [path] if path.is_file() else list(path.rglob("*.py"))
        for py in files:
            assert BANNED_METHOD not in py.read_text(encoding="utf-8")


def test_http_transport_sends_only_snapshot_methods():
    from mcp_tool_drift.model import ServerSpec
    from mcp_tool_drift.transport import HttpTransport

    seen: list[str] = []

    def opener(req, timeout=None):
        body = json.loads(req.data.decode())
        seen.append(body["method"])
        if body["method"] == "notifications/initialized":
            return _Resp(b"")
        if body["method"] == "initialize":
            payload = {"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2024-11-05"}}
        elif body["method"] == "tools/list":
            payload = {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]},
            }
        else:
            raise AssertionError(body["method"])
        return _Resp(json.dumps(payload).encode())

    server = ServerSpec(client="cursor", name="remote", command=None, args=(), url="http://127.0.0.1:9/mcp", env={})
    tools = HttpTransport(opener=opener).list_tools(server, timeout=1)
    assert [tool["name"] for tool in tools] == ["echo"]
    assert seen == ["initialize", "notifications/initialized", "tools/list"]
    assert BANNED_METHOD not in seen


def test_guard_rejects_other_methods():
    from mcp_tool_drift.transport import MethodRejected, guard_method

    guard_method("initialize")
    guard_method("tools/list")
    try:
        guard_method("resources/read")
    except MethodRejected:
        return
    raise AssertionError("expected MethodRejected")


class _Resp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
