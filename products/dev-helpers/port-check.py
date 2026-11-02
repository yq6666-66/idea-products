#!/usr/bin/env python3
"""port-check: who is listening on a local port? (v1, read-only, never kills).

Usage:
    python3 port-check.py 7897 5173 3000

For each port it reports:
- listening or free, from a plain TCP connect to 127.0.0.1;
- the owning process when `ss -tlnp` (Linux) or `netstat -ano`
  (Windows) can tell us, otherwise "process unknown".

It never kills a process, never changes a config, and never touches
anything outside the ports you name on the command line.
"""
import argparse
import re
import socket
import subprocess
import sys


def is_listening(port):
    sock = socket.socket()
    sock.settimeout(1)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def process_for_port(port):
    # Linux: ss -tlnp prints "users:(("name",pid=123,fd=..))" per line.
    try:
        out = subprocess.run(["ss", "-tlnp"], capture_output=True,
                             text=True, timeout=10).stdout
        for line in out.splitlines():
            if re.search(rf":{port}\b", line):
                m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                if m:
                    return f"{m.group(1)} (pid {m.group(2)})"
                return "listening, process not shown by ss"
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Windows: netstat -ano, last column is the PID.
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, timeout=10).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper().startswith("TCP"):
                local = parts[1]
                if local.rsplit(":", 1)[-1] == str(port) and parts[3] == "LISTENING":
                    return f"pid {parts[4]} (look up the name in Task Manager)"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "process unknown (ss/netstat unavailable or silent)"


def main():
    ap = argparse.ArgumentParser(description="Read-only local port check.")
    ap.add_argument("ports", nargs="+", type=int, help="Ports to check, e.g. 7897 5173")
    args = ap.parse_args()
    for port in args.ports:
        if not 1 <= port <= 65535:
            print(f"  {port}: invalid port, skipped")
            continue
        if is_listening(port):
            print(f"  {port}: LISTENING, owner: {process_for_port(port)}")
        else:
            print(f"  {port}: free (nothing listening on 127.0.0.1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
