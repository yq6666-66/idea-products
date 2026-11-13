#!/usr/bin/env python3
"""Read-only health audit for git submodules across repositories.

Given a root directory, it finds every local git repository under
it and checks all of their submodules, including nested ones, then
prints one table grouped by repository and sorted by severity.

Usage:
    python3 submodule-audit.py <root-dir> [--json]

Exit code is 0 when the scan finishes, even when problems are
found (the problems are written in the table); 2 when the root
directory does not exist or is not a directory.

Checks, each decided by a git command, never by guessing:
  1. uninitialized: git submodule status shows a '-' prefix;
  2. commit mismatch: a '+' prefix, the checked-out commit differs
     from the commit recorded in the parent index;
  3. merge conflict: a 'U' prefix;
  4. URL drift: the URL in .gitmodules differs from the URL
     registered in .git/config (compared with git config
     --get-regexp on both sides; a missing side is reported
     separately, not silently skipped);
  5. nested submodule not initialized: git submodule status
     --recursive covers nested levels, a '-' there is reported;
  6. the commit recorded in the parent index does not exist on
     the submodule remote: probed read-only, first with
     git ls-remote <url> (a SHA in the ref tips means it exists),
     then, only when it is not a ref tip, by fetching that one
     SHA into a temporary bare repository and checking the
     object is there. A plain "ls-remote <url> <sha>" does NOT
     work for this: ls-remote patterns match ref names, never
     SHAs, so it returns empty even for a commit the remote has.
     Unreachable remotes make this "unverified" instead of a
     false conclusion;
  7. the submodule remote is unreachable: ls-remote failing with
     return code 128, a timeout, a 404, or an authentication
     failure, labelled separately.

Red lines: never runs git submodule init, update or sync, never
writes .gitmodules or .git/config, never deletes objects. Remote
URLs are printed redacted (host and path only; a URL carrying a
username or password shows only its host). Suggestions are printed
as text only, never executed.

Known limits:
  - ls-remote needs a network; offline, checks 6 and 7 are
    "unverified", never a false conclusion.
  - Authentication failure and unreachable are hard to tell apart
    without credentials; they are labelled from git's error text,
    and written as "suspected authentication failure" when unsure.
  - A shallow-cloned submodule can be misread as a missing
    commit because its history is incomplete; shallow clones are
    flagged and the conclusion is marked reference-only.
  - The fetch-by-SHA fallback needs the remote to allow fetching
    a single SHA (most hosts do for reachable commits); a remote
    that refuses it can make a present commit look missing, so
    that conclusion is only drawn after the ref-tip check misses
    and the fetch explicitly reports "not our ref".
  - This is the local-clone view only: whether the parent remote
    and the submodule remote agree (for example a fork relation)
    is out of scope.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
    "build",
}
LS_REMOTE_TIMEOUT = 15

STATUS_RE = re.compile(r"^([-+U ])(\w{40}) (\S+)(?: \(.*\))?$")
CONFIG_RE = re.compile(r"^submodule\.(.+)\.url\s+(.*)$")

# Severity order: merge conflict first, then a commit missing on
# the remote, then uninitialized and mismatch, then URL drift and
# unreachable remotes (an unreachable remote may just be the
# network, so it is also marked "needs recheck").
SEVERITY = {
    "合并冲突": 0,
    "远端不存在的提交": 1,
    "未初始化": 2,
    "提交不一致": 2,
    "URL漂移": 3,
    "远端不可达": 3,
    "未核实": 4,
}


def run_git(directory, *args, timeout=30):
    try:
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def redact_url(url):
    """Show only the host and path of a remote URL."""
    url = url.strip()
    if "://" in url:
        parts = urlsplit(url)
        host = parts.hostname or ""
        return f"{parts.scheme}://{host}{parts.path}"
    if "@" in url:
        after_at = url.split("@", 1)[1]
        host = after_at.split(":", 1)[0]
        rest = after_at[len(host):]
        return f"{host}{rest}"
    return url


def discover_repos(root):
    """Return the git repositories directly under root.

    A directory containing .git is one repository; its own
    subdirectories are not searched again (a submodule is a
    repository too, but it belongs to its parent's checks).
    """
    repos = []
    for dirpath, dirnames, _filenames in os.walk(root):
        current = Path(dirpath)
        if (current / ".git").exists():
            repos.append(current)
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    return sorted(repos)


def config_urls(directory, gitmodules=False):
    """Return {submodule name: url} from .gitmodules or .git/config."""
    if gitmodules:
        args = ["config", "-f", ".gitmodules", "--get-regexp",
                r"^submodule\..*\.url$"]
    else:
        args = ["config", "--local", "--get-regexp",
                r"^submodule\..*\.url$"]
    result = run_git(directory, *args)
    urls = {}
    if result is None or result.returncode != 0:
        return urls
    for line in result.stdout.splitlines():
        match = CONFIG_RE.match(line)
        if match:
            urls[match.group(1)] = match.group(2).strip()
    return urls


def submodule_paths(directory):
    """Return {submodule name: path} from .gitmodules."""
    result = run_git(directory, "config", "-f", ".gitmodules",
                     "--get-regexp", r"^submodule\..*\.path$")
    paths = {}
    if result is None or result.returncode != 0:
        return paths
    for line in result.stdout.splitlines():
        match = re.match(r"^submodule\.(.+)\.path\s+(.*)$", line)
        if match:
            paths[match.group(1)] = match.group(2).strip()
    return paths


def index_sha(owner_dir, name):
    """Return the SHA recorded in the index for a submodule."""
    result = run_git(owner_dir, "ls-files", "-s", "--", name)
    if result is None or result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "160000":
            return parts[1]
    return None


def is_shallow(worktree):
    result = run_git(worktree, "rev-parse",
                     "--is-shallow-repository")
    return (result is not None and result.returncode == 0
            and result.stdout.strip() == "true")


def classify_failure(stderr):
    """Classify a failed git remote call from its error text."""
    lowered = (stderr or "").lower()
    if "404" in stderr or "not found" in lowered:
        return "not_found"
    if ("authentication failed" in lowered
            or "permission denied" in lowered
            or "could not read username" in lowered
            or "fatal: authentication" in lowered):
        return "auth_failed"
    return "unreachable"


def probe_remote(url, sha):
    """Probe one SHA on a remote. Returns (outcome, detail).

    outcome is one of: exists, missing, unreachable, not_found,
    auth_failed, unverified.

    ls-remote patterns match ref names, never SHAs, so passing
    the SHA as a pattern always returns empty. Instead, list the
    ref tips first (a SHA there means it exists), and only when
    it is not a tip, fetch that one SHA into a temporary bare
    repository and check the object is there. The temporary
    repository lives outside the scanned tree and is deleted
    afterwards; nothing in the scanned repositories is touched.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", url],
            capture_output=True, text=True,
            timeout=LS_REMOTE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "unverified", "ls-remote timed out"
    if result.returncode != 0:
        return classify_failure(result.stderr), ""
    if sha in result.stdout:
        return "exists", ""
    import tempfile
    try:
        with tempfile.TemporaryDirectory(
                prefix="submodule-audit-probe-") as tmp:
            bare = Path(tmp) / "probe.git"
            init = subprocess.run(
                ["git", "init", "-q", "--bare", str(bare)],
                capture_output=True, text=True,
                timeout=LS_REMOTE_TIMEOUT)
            if init.returncode != 0:
                return "unverified", "could not create probe repo"
            try:
                fetch = subprocess.run(
                    ["git", "-C", str(bare), "fetch", "-q", url, sha],
                    capture_output=True, text=True,
                    timeout=LS_REMOTE_TIMEOUT)
            except subprocess.TimeoutExpired:
                return "unverified", "fetch timed out"
            if fetch.returncode == 0:
                return "exists", ""
            lowered = (fetch.stderr or "").lower()
            if ("not our ref" in lowered
                    or "couldn't find remote ref" in lowered):
                return "missing", ""
            return classify_failure(fetch.stderr), ""
    except subprocess.TimeoutExpired:
        return "unverified", "probe timed out"


def audit_repo(repo, root):
    """Return (rows, has_submodules) for one repository."""
    rows = []

    def add(submodule, level, issue, suggestion):
        rows.append({
            "repo": str(repo.relative_to(root)) or ".",
            "submodule": submodule,
            "level": level,
            "issue": issue,
            "suggestion": suggestion,
        })

    result = run_git(repo, "submodule", "status", "--recursive")
    entries = []
    if result is not None and result.returncode == 0:
        for line in result.stdout.splitlines():
            match = STATUS_RE.match(line)
            if match:
                entries.append({
                    "prefix": match.group(1),
                    "sha": match.group(2),
                    "path": match.group(3),
                })
    if not entries:
        return rows, False

    # URL maps per owner directory: the top repository and each
    # outer submodule that itself owns nested submodules.
    owner_dirs = {repo}
    for entry in entries:
        parent = Path(entry["path"]).parent
        if str(parent) != ".":
            owner_dirs.add(repo / parent)
    maps = {}
    for owner in owner_dirs:
        maps[owner] = {
            "gitmodules": config_urls(owner, gitmodules=True),
            "config": config_urls(owner),
            "paths": submodule_paths(owner),
        }

    # URL drift, per owner directory and submodule name.
    for owner, data in maps.items():
        prefix = ""
        if owner != repo:
            prefix = str(owner.relative_to(repo)) + "/"
        names = set(data["gitmodules"]) | set(data["config"])
        for name in sorted(names):
            path = prefix + data["paths"].get(name, name)
            in_modules = name in data["gitmodules"]
            in_config = name in data["config"]
            if in_modules and in_config:
                if data["gitmodules"][name] != data["config"][name]:
                    add(path, "URL漂移",
                        f".gitmodules 记的远端是 "
                        f"{redact_url(data['gitmodules'][name])}，"
                        f".git/config 注册的是 "
                        f"{redact_url(data['config'][name])}，"
                        f"改过 .gitmodules 后没跑过 sync",
                        f"git submodule sync -- {path}")
            elif in_modules:
                add(path, "URL漂移",
                    ".gitmodules 里有，.git/config 里没有注册",
                    f"git submodule update --init -- {path}")
            else:
                add(path, "URL漂移",
                    ".git/config 里有注册，.gitmodules 里缺失",
                    "检查 .gitmodules 是否误删该子模块")

    # Status prefixes and the remote probe, per submodule.
    for entry in entries:
        path = entry["path"]
        prefix = entry["prefix"]
        owner = repo
        parent = Path(path).parent
        if str(parent) != ".":
            owner = repo / parent
        leaf = Path(path).name
        owner_data = maps.get(owner, {"gitmodules": {}, "config": {},
                                      "paths": {}})
        name = None
        for candidate, candidate_path in owner_data["paths"].items():
            if candidate_path == leaf:
                name = candidate
                break
        if name is None:
            for candidate, candidate_path in owner_data["paths"].items():
                if candidate_path == path:
                    name = candidate
                    break
        url = None
        if name is not None:
            url = (owner_data["config"].get(name)
                   or owner_data["gitmodules"].get(name))
        recorded = index_sha(owner, leaf) or entry["sha"]
        if prefix == "-":
            add(path, "未初始化",
                "子模块目录是空的，尚未初始化",
                f"git submodule update --init -- {path}")
        elif prefix == "+":
            add(path, "提交不一致",
                f"子模块检出的提交与父仓库索引记录的 "
                f"{recorded[:7]} 不一致",
                f"git submodule update -- {path}")
        elif prefix == "U":
            add(path, "合并冲突",
                "子模块存在合并冲突",
                f"git -C {path} status")
        if url is None:
            add(path, "未核实",
                "找不到子模块的远端 URL，无法探测",
                "检查 .gitmodules 是否记了该子模块的 URL")
            continue
        outcome, _detail = probe_remote(url, recorded)
        if outcome == "exists":
            continue
        if outcome == "missing":
            issue = (f"父仓库索引记的提交 {recorded[:7]} "
                     f"在远端 {redact_url(url)} 上不存在")
            worktree = repo / path
            if worktree.is_dir() and is_shallow(worktree):
                issue += "（浅克隆，结论仅供参考）"
            add(path, "远端不存在的提交", issue,
                f"git ls-remote {redact_url(url)} | grep "
                f"{recorded[:7]} 复查，"
                f"或确认子模块提交是否已推送")
        elif outcome == "not_found":
            add(path, "远端不可达",
                f"远端 {redact_url(url)} 返回 404，需复查",
                f"git ls-remote {redact_url(url)} 复查远端地址")
        elif outcome == "auth_failed":
            add(path, "远端不可达",
                f"远端 {redact_url(url)} 疑似认证失败，需复查",
                f"git ls-remote {redact_url(url)} 复查凭证")
        elif outcome == "unreachable":
            add(path, "远端不可达",
                f"远端 {redact_url(url)} 不可达，需复查",
                f"git ls-remote {redact_url(url)} 复查网络与地址")
        else:
            add(path, "未核实",
                f"远端 {redact_url(url)} 探测超时，无法确认提交"
                f" {recorded[:7]} 是否存在",
                f"git ls-remote {redact_url(url)} 复查")
    rows.sort(key=lambda r: (SEVERITY[r["level"]], r["submodule"]))
    return rows, True


def collect(root):
    """Return (rows, repo_count, with_submodules)."""
    repos = discover_repos(root)
    rows = []
    with_submodules = 0
    for repo in repos:
        repo_rows, has_submodules = audit_repo(repo, root)
        if has_submodules:
            with_submodules += 1
        rows.extend(repo_rows)
    return rows, len(repos), with_submodules


def print_table(rows):
    if not rows:
        print("  (no problems found)")
        return
    grouped = {}
    for row in rows:
        grouped.setdefault(row["repo"], []).append(row)
    headers = ("SUBMODULE", "LEVEL", "ISSUE", "SUGGESTION")
    for repo, repo_rows in grouped.items():
        print(f"\n{repo}")
        table = [headers] + [(r["submodule"], r["level"], r["issue"],
                              r["suggestion"]) for r in repo_rows]
        widths = [max(len(r[i]) for r in table) for i in range(4)]
        for row in table:
            print("  " + "  ".join(cell.ljust(widths[i])
                                   for i, cell in enumerate(row)))


def print_summary(rows, repo_count, with_submodules, stream):
    unverified = sum(1 for r in rows if r["level"] == "未核实")
    print(f"共扫 {repo_count} 个仓库，其中 {with_submodules} 个含子模块，"
          f"问题 {len(rows)} 条（未核实 {unverified} 条）",
          file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Cross-repo git submodule health audit, read-only.")
    parser.add_argument("root", help="root directory to scan")
    parser.add_argument("--json", action="store_true",
                        help="output issues as a JSON array")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    rows, repo_count, with_submodules = collect(root)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        print_summary(rows, repo_count, with_submodules, sys.stderr)
    else:
        print_table(rows)
        print_summary(rows, repo_count, with_submodules, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
