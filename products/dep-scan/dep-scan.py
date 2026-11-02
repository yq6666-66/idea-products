#!/usr/bin/env python3
"""dep-scan: dependency freshness and vulnerability report (v2, read-only).

Usage:
    python3 dep-scan.py <project-dir> [--check-latest]

What it does:
- Reads package.json dependencies/devDependencies and requirements.txt
  (whatever exists; missing files are reported, not invented).
- For Python packages, compares the declared spec with the version
  installed in the current environment (importlib.metadata).
  For Node packages, compares with node_modules/<pkg>/package.json
  when present.
- With --check-latest, it also fetches the latest version from PyPI
  (Python) or the npm registry (Node) and marks OUTDATED / UP-TO-DATE.
  If the registry cannot be reached it says UNKNOWN, never invents
  a version.
- It parses pip audit / npm audit JSON when available and lists
  vulnerabilities sorted by severity (critical, high, moderate, low,
  info; pip audit has no severity field, so those are listed last
  with severity unknown). If an audit tool is absent it says so
  instead of inventing vulnerability data.

What it never does: upgrade, install, uninstall, or edit any file.
The output is an upgrade list only; upgrading is a separate,
human decision.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

try:
    from importlib import metadata as importlib_metadata
except ImportError:  # Python < 3.8
    importlib_metadata = None

SEVERITY_ORDER = {"critical": 0, "high": 1, "moderate": 2, "low": 3, "info": 4, "unknown": 5}


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


def version_key(version):
    parts = []
    for piece in re.split(r"[.\-+_]", str(version)):
        if piece.isdigit():
            parts.append((0, int(piece), ""))
        else:
            parts.append((1, 0, piece))
    return parts


def latest_version(kind, name):
    urls = {
        "python": f"https://pypi.org/pypi/{name}/json",
        "node": f"https://registry.npmjs.org/{name}/latest",
    }
    try:
        req = urllib.request.Request(urls[kind], headers={"User-Agent": "dep-scan/2"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        if kind == "python":
            return data["info"]["version"]
        return data["version"]
    except Exception:
        return None


def freshness(installed, latest):
    if not installed or not latest:
        return "UNKNOWN"
    try:
        if version_key(installed) < version_key(latest):
            return "OUTDATED"
        if version_key(installed) == version_key(latest):
            return "UP-TO-DATE"
        return "NEWER-THAN-LATEST"
    except Exception:
        return "UNKNOWN"


def pip_audit_vulns(root):
    try:
        proc = subprocess.run(["pip", "audit", "--format", "json"], cwd=root,
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None, "pip audit not available or timed out, skipped"
    if proc.returncode != 0 and not proc.stdout.strip():
        return None, "pip audit unavailable here, skipped"
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return None, "pip audit output could not be parsed, inspect it before acting"
    vulns = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            vulns.append({
                "package": dep.get("name", "?"),
                "id": vuln.get("id", "?"),
                "severity": "unknown",
                "fix": ", ".join(vuln.get("fix_versions", [])) or "no fix listed",
            })
    return vulns, None


def npm_audit_vulns(root):
    try:
        proc = subprocess.run(["npm", "audit", "--json"], cwd=root,
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None, "npm audit not available or timed out, skipped"
    if not proc.stdout.strip():
        return None, "npm audit unavailable here, skipped"
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return None, "npm audit output could not be parsed, inspect it before acting"
    vulns = []
    for name, info in (data.get("vulnerabilities") or {}).items():
        severity = str(info.get("severity", "unknown")).lower()
        via = info.get("via")
        via_text = ""
        if isinstance(via, list):
            via_text = ", ".join(str(v.get("title", v)) if isinstance(v, dict) else str(v) for v in via)
        elif via:
            via_text = str(via)
        fix = info.get("fixAvailable")
        fix_text = "no fix listed"
        if isinstance(fix, dict):
            fix_text = f"fix in {fix.get('version', '?')}"
        elif fix is True:
            fix_text = "fix available"
        vulns.append({"package": name, "id": via_text or name,
                      "severity": severity, "fix": fix_text})
    return vulns, None


def main():
    ap = argparse.ArgumentParser(description="Read-only dependency report.")
    ap.add_argument("project_dir", help="Project directory to inspect")
    ap.add_argument("--check-latest", action="store_true",
                    help="Also compare installed versions with the latest registry version")
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
                extra = ""
                if args.check_latest:
                    latest = latest_version("node", name)
                    extra = f", latest {latest or 'UNKNOWN'}, {freshness(installed, latest)}"
                print(f"  node {section} {name}: declared {spec}, "
                      f"installed {installed or 'not found in node_modules'}{extra}")
    else:
        print("  no package.json")

    req_txt = os.path.join(root, "requirements.txt")
    if os.path.isfile(req_txt):
        for name, spec in parse_requirements(req_txt):
            installed = installed_python_version(name)
            extra = ""
            if args.check_latest:
                latest = latest_version("python", name)
                extra = f", latest {latest or 'UNKNOWN'}, {freshness(installed, latest)}"
            print(f"  python {name}: declared {spec}, "
                  f"installed {installed or 'not installed here'}{extra}")
    else:
        print("  no requirements.txt")

    all_vulns = []
    for label, getter in (("pip audit", pip_audit_vulns), ("npm audit", npm_audit_vulns)):
        vulns, note = getter(root)
        if note:
            print(f"  audit: {note}")
            continue
        all_vulns.extend(vulns or [])
    if all_vulns:
        all_vulns.sort(key=lambda v: (SEVERITY_ORDER.get(v["severity"], 5), v["package"], v["id"]))
        print("  vulnerabilities (sorted by severity):")
        for vuln in all_vulns:
            print(f"    [{vuln['severity']}] {vuln['package']}: {vuln['id']} (fix: {vuln['fix']})")
    else:
        print("  vulnerabilities: none reported by available audits (or audits unavailable)")
    print("  note: this is an upgrade list only; nothing was upgraded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
