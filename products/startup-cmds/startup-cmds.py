#!/usr/bin/env python3
"""Read-only startup-command summary for one project directory.

Reads package.json, Makefile, justfile and pyproject.toml and lists
every runnable startup command found, without executing anything,
without changing any file and without installing anything.

Usage:
    python3 startup-cmds.py <project-dir> [--json]

Output (table mode):
    NAME  SOURCE  SECTION  COMMAND, one row per command, followed by
    a summary line: files scanned, commands found, files skipped
    with reasons. The same command name in several files is listed
    on separate rows, never merged.

Output (--json mode):
    A JSON array of command objects to stdout; the summary goes to
    stderr so the JSON stays machine-readable.

Known limits, stated not hidden:
    - Makefile variables and includes are not expanded; a command
      body containing $(...) is shown verbatim.
    - justfile parameter defaults are not expanded; parameters are
      shown only as placeholders.
    - pyproject.toml needs Python 3.11+ tomllib; on older versions
      the file is reported as unsupported, not silently skipped.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

MAKEFILE_TARGET = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:\s*(.*)$")
JUSTFILE_RECIPE = re.compile(r"^([A-Za-z0-9_\-]+)(.*):\s*(.*)$")
JUSTFILE_PARAM = re.compile(r"([A-Za-z0-9_]+)\s*(?:=|$)")

# command: name, source_file, source_section, command_body
# skipped: file, reason
# notes: short non-error notes, e.g. pyproject without a scripts table


def parse_package_json(directory, commands, skipped, notes):
    path = directory / "package.json"
    if not path.exists():
        skipped.append((path.name, "missing"))
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        skipped.append((path.name, f"unreadable: {exc}"))
        return
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        notes.append("package.json: no scripts table")
        return
    for name, body in scripts.items():
        commands.append((name, path.name, "scripts", str(body)))


def parse_makefile(directory, commands, skipped, notes):
    path = directory / "Makefile"
    if not path.exists():
        skipped.append((path.name, "missing"))
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        skipped.append((path.name, f"unreadable: {exc}"))
        return
    for line in text.splitlines():
        if not line or line[0] in " \t#":
            continue
        match = MAKEFILE_TARGET.match(line)
        if not match:
            continue
        name, rest = match.group(1), match.group(2).strip()
        if name.startswith(".") or "%" in name:
            continue
        comment = ""
        if "#" in rest:
            comment = rest[rest.index("#"):].strip()
        body = f"make {name}"
        if comment:
            body = f"{body} {comment}"
        commands.append((name, path.name, "Makefile target", body))


def parse_justfile(directory, commands, skipped, notes):
    path = directory / "justfile"
    if not path.exists():
        skipped.append((path.name, "missing"))
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        skipped.append((path.name, f"unreadable: {exc}"))
        return
    for line in text.splitlines():
        if not line or line[0] in " \t#":
            continue
        match = JUSTFILE_RECIPE.match(line)
        if not match:
            continue
        name, params_text = match.group(1), match.group(2).strip()
        if name.startswith("_"):
            continue
        params = JUSTFILE_PARAM.findall(params_text)
        display = name
        if params:
            display = name + " " + " ".join(f"<{p}>" for p in params)
        commands.append((display, path.name, "justfile recipe",
                         f"just {display}"))


def parse_pyproject(directory, commands, skipped, notes):
    path = directory / "pyproject.toml"
    if not path.exists():
        skipped.append((path.name, "missing"))
        return
    if tomllib is None:
        skipped.append((path.name, "unsupported: needs Python 3.11+ tomllib"))
        return
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        skipped.append((path.name, f"unreadable: {exc}"))
        return
    found = False
    project = data.get("project", {}) if isinstance(data, dict) else {}
    if isinstance(project, dict) and isinstance(project.get("scripts"), dict):
        found = True
        for name, body in project["scripts"].items():
            commands.append((name, path.name, "project.scripts", str(body)))
    tool = data.get("tool", {}) if isinstance(data, dict) else {}
    poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    if isinstance(poetry, dict) and isinstance(poetry.get("scripts"), dict):
        found = True
        for name, body in poetry["scripts"].items():
            commands.append((name, path.name, "tool.poetry.scripts",
                             str(body)))
    if not found:
        notes.append("pyproject.toml: no scripts table")


def collect(directory):
    commands, skipped, notes = [], [], []
    parse_package_json(directory, commands, skipped, notes)
    parse_makefile(directory, commands, skipped, notes)
    parse_justfile(directory, commands, skipped, notes)
    parse_pyproject(directory, commands, skipped, notes)
    # Files counted as scanned: the four candidates minus the ones
    # that were missing or unreadable. A file with no scripts table
    # was read successfully, so it counts as scanned, not skipped.
    scanned = sum(1 for name in ("package.json", "Makefile", "justfile",
                                 "pyproject.toml")
                  if name not in {s[0] for s in skipped})
    return commands, skipped, notes, scanned


def print_table(commands):
    headers = ("NAME", "SOURCE", "SECTION", "COMMAND")
    rows = [headers] + [(c[0], c[1], c[2], c[3]) for c in commands]
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    for row in rows:
        print("  ".join(cell.ljust(widths[i])
                        for i, cell in enumerate(row)))


def print_summary(commands, skipped, notes, scanned, stream):
    print(f"scanned: {scanned} file(s), commands: {len(commands)}, "
          f"skipped: {len(skipped)} file(s)", file=stream)
    for name, reason in skipped:
        print(f"  skipped {name}: {reason}", file=stream)
    for note in notes:
        print(f"  note {note}", file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="List a project's startup commands, read-only.")
    parser.add_argument("directory", help="project directory to scan")
    parser.add_argument("--json", action="store_true",
                        help="output a JSON array of command objects")
    args = parser.parse_args(argv)
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    commands, skipped, notes, scanned = collect(directory)
    if args.json:
        objects = [{"name": c[0], "source_file": c[1],
                    "source_section": c[2], "command": c[3]}
                   for c in commands]
        print(json.dumps(objects, ensure_ascii=False, indent=2))
        print_summary(commands, skipped, notes, scanned, sys.stderr)
    else:
        print_table(commands)
        print_summary(commands, skipped, notes, scanned, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
