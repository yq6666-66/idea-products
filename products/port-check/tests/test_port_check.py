import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "port-check.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=60)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_listening(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def test_free_port_reported_free():
    port = free_port()
    result = run(port)
    assert result.returncode == 0
    assert f"{port}: free" in result.stdout


def test_listening_reports_owner_command_and_does_not_kill():
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_listening(port), "test server did not start listening"
        result = run(port)
        assert result.returncode == 0
        assert f"{port}: LISTENING" in result.stdout
        assert "http.server" in result.stdout
        assert server.poll() is None, "port-check must not kill the process it reports"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def test_common_flag_lists_dev_ports():
    result = run("--common")
    assert result.returncode == 0
    for port in (7897, 5173, 3000, 8000, 8080):
        assert f"{port}:" in result.stdout


def test_invalid_port_skipped():
    result = run(99999)
    assert result.returncode == 0
    assert "invalid port, skipped" in result.stdout


def test_demo_runs_and_shows_listening():
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "demo.py")],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "LISTENING" in result.stdout
    assert "7897:" in result.stdout
