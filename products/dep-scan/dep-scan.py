#!/usr/bin/env python3
"""dep-scan: dependency freshness report (v1, read-only, never upgrades).

Usage:
    python3 dep-scan.py <project-dir>

What it does:
- Reads package.json dependencies/devDependencies and requirements.txt
  (whatever exists; missing files are reported, not invented).
- For Python packages, compares the declared spec with the version
  installed in the current environment (importlib.metadata).
  For Node packages, compares with node_modules/<pkg>/package.json
  when present.
- If `pip audit` or `npm audit` is available in the project, it runs
  the read-only audit and prints a short summary; if the tool is
  absent it says so instead of inventing vulnerability data.

What it never does: upgrade, install, uninstall, or edit any file.
"""
import argparse
import json
import os
import re
import subprocess
import sys

try:
    from importlib import metadata as importlib_metadata
except ImportError:  # Python < 3.8
    importlib_metadata = None


def parse_requirements(path):
    deps = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            name = re.split(r"[<>=!~\s\[]", line, maxsplit=1)[0].strip()
            if name:
                deps.append((name, line))
    return deps


def installed_python_version(name):
    if importlib_metadata is None:
        return None
    try:
        return importlib_metadata.version(name)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Read-only dependency report.")
    ap.add_argument("project_dir", help="Project directory to inspect")
    args = ap.parse_args()
    root = args.project_dir
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    print(f"project: {root}")

    pkg_json = os.path.join(root, "package.json")
    if os.path.isfile(pkg_json):
        try:
            data = json.load(open(pkg_json, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"package.json unreadable: {exc}")
            data = {}
        for section in ("dependencies", "devDependencies"):
            for name, spec in (data.get(section) or {}).items():
                installed = None
                mod_pkg = os.path.join(root, "node_modules", name, "package.json")
                if os.path.isfile(mod_pkg):
                    try:
                        installed = json.load(open(mod_pkg, encoding="utf-8")).get("version")
                    except (OSError, ValueError):
                        installed = None
                print(f"  node {section} {name}: declared {spec}, "
                      f"installed {installed or 'not found in node_modules'}")
    else:
        print("  no package.json")

    req_txt = os.path.join(root, "requirements.txt")
    if os.path.isfile(req_txt):
        for name, spec in parse_requirements(req_txt):
            installed = installed_python_version(name)
            print(f"  python {name}: declared {spec}, "
                  f"installed {installed or 'not installed here'}")
    else:
        print("  no requirements.txt")

    # Optional read-only audits, only when the tool exists.
    for tool, cmd in (("pip audit", ["pip", "audit", "--format", "json"]),
                      ("npm audit", ["npm", "audit", "--json"])):
        try:
            proc = subprocess.run(cmd, cwd=root, capture_output=True,
                                  text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            print(f"  audit: {tool} not available or timed out, skipped")
            continue
        if proc.returncode != 0 and not proc.stdout.strip():
            print(f"  audit: {tool} unavailable here, skipped")
            continue
        print(f"  audit: {tool} ran (exit {proc.returncode}); "
              f"full output not summarised here, inspect it before acting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
