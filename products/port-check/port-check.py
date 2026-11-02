#!/usr/bin/env python3
"""port-check: who is listening on a local port? (v2, read-only, never kills).

Usage:
    python3 port-check.py 7897 5173 3000
    python3 port-check.py --common

For each port it reports:
- listening or free, from a plain TCP connect to 127.0.0.1;
- the owning process when `ss -tlnp` (Linux) or `netstat -ano`
  (Windows) can tell us, otherwise "process unknown";
- the process startup command when it can be read: /proc/<pid>/cmdline
  on Linux, or wmic/tasklist on Windows. If it cannot be read, it
  says so instead of guessing.

--common checks the usual dev ports: 7897 5173 3000 8000 8080.

It never kills a process, never changes a config, and never touches
anything outside the ports you name on the command line.
"""
import argparse
import re
import socket
import subprocess
import sys

COMMON_PORTS = [7897, 5173, 3000, 8000, 8080]


def is_listening(port):
    sock = socket.socket()
    sock.settimeout(1)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def process_for_port(port):
    """Return (label, pid or None)."""
    try:
        out = subprocess.run(["ss", "-tlnp"], capture_output=True,
                             text=True, timeout=10).stdout
        for line in out.splitlines():
            if re.search(rf":{port}\b", line):
                m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                if m:
                    return f"{m.group(1)} (pid {m.group(2)})", int(m.group(2))
                return "listening, process not shown by ss", None
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, timeout=10).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper().startswith("TCP"):
                local = parts[1]
                if local.rsplit(":", 1)[-1] == str(port) and parts[3] == "LISTENING":
                    pid = int(parts[4]) if parts[4].isdigit() else None
                    name = None
                    try:
                        task = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {parts[4]}", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, timeout=10).stdout
                        if task.strip():
                            name = task.strip().split('","')[0].strip('"')
                    except (OSError, subprocess.TimeoutExpired, ValueError):
                        pass
                    label = f"{name} (pid {parts[4]})" if name else f"pid {parts[4]}"
                    return label, pid
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "process unknown (ss/netstat unavailable or silent)", None


def command_for_pid(pid):
    if pid is None:
        return "command unknown (no pid)"
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            parts = [p.decode(errors="replace") for p in fh.read().split(b"\0") if p]
        if parts:
            return " ".join(parts)
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/format:list"],
            capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.startswith("CommandLine="):
                cmd = line.split("=", 1)[1].strip()
                if cmd:
                    return cmd
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "command unknown (unreadable or not permitted)"


def main():
    ap = argparse.ArgumentParser(description="Read-only local port check.")
    ap.add_argument("ports", nargs="*", type=int, help="Ports to check, e.g. 7897 5173")
    ap.add_argument("--common", action="store_true",
                    help="Check the usual dev ports: 7897 5173 3000 8000 8080")
    args = ap.parse_args()
    ports = list(dict.fromkeys((args.ports or []) + (COMMON_PORTS if args.common else [])))
    if not ports:
        ap.print_usage(sys.stderr)
        print("pass ports, or use --common", file=sys.stderr)
        return 2
    for port in ports:
        if not 1 <= port <= 65535:
            print(f"  {port}: invalid port, skipped")
            continue
        if is_listening(port):
            label, pid = process_for_port(port)
            print(f"  {port}: LISTENING, owner: {label}")
            print(f"         command: {command_for_pid(pid)}")
        else:
            print(f"  {port}: free (nothing listening on 127.0.0.1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
