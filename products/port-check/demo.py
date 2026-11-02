#!/usr/bin/env python3
"""Simple demo for port-check: starts its own temp HTTP server,
runs port-check on that port and on --common, prints both, then
stops its own server.

Usage:
    python3 demo.py

It touches nothing outside its own temp server, and it never kills
any process except the server it started itself.
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


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


def main():
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_listening(port):
            print("demo server did not start listening", file=sys.stderr)
            return 1
        print(f"=== port-check on demo server port {port} ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "port-check.py"), str(port)],
                       check=True)
        print("\n=== port-check --common ===", flush=True)
        subprocess.run([sys.executable, str(HERE / "port-check.py"), "--common"],
                       check=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    print("\nDemo server stopped. No other process was touched.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
