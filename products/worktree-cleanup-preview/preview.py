#!/usr/bin/env python3
"""Read-only preview of orphan/stale worktrees and merged local branches."""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(repo: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def guess_base(repo: Path) -> str:
    for name in ("main", "master"):
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", name],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            return name
    raise SystemExit("cannot find main/master; pass --base")


def parse_worktrees(porcelain: str) -> list[dict]:
    items: list[dict] = []
    cur: dict = {}
    for line in porcelain.splitlines():
        if not line.strip():
            if cur:
                items.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            if cur:
                items.append(cur)
            cur = {"path": line[len("worktree ") :]}
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            ref = line[len("branch ") :]
            cur["branch"] = ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
        elif line == "detached":
            cur["detached"] = True
        elif line == "bare":
            cur["bare"] = True
        elif line == "locked" or line.startswith("locked "):
            cur["locked"] = True
        elif line == "prunable" or line.startswith("prunable "):
            cur["prunable"] = True
    if cur:
        items.append(cur)
    return items


def last_commit_time(repo: Path, ref: str) -> str:
    out = run(repo, "log", "-1", "--format=%cI", ref).strip()
    return out or "?"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("repo", type=Path, help="path to git repo")
    p.add_argument("--base", default=None, help="integration branch (default: main/master)")
    args = p.parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").exists() and not (repo / "HEAD").exists():
        # allow bare / worktree paths: still need git dir
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"not a git repo: {repo}")
    base = args.base or guess_base(repo)

    print(f"# worktree-cleanup-preview")
    print(f"repo: {repo}")
    print(f"base: {base}")
    print(f"generated_at: {datetime.now(timezone.utc).isoformat()}")
    print()

    wts = parse_worktrees(run(repo, "worktree", "list", "--porcelain"))
    primary = wts[0]["path"] if wts else None
    print("## worktrees (candidates)")
    found_wt = False
    for wt in wts:
        path = wt.get("path", "?")
        if wt.get("bare"):
            continue
        flags = []
        if path == primary:
            flags.append("primary")
        if wt.get("detached"):
            flags.append("detached")
        if wt.get("locked"):
            flags.append("locked")
        if wt.get("prunable"):
            flags.append("prunable/orphan")
        branch = wt.get("branch")
        head = wt.get("head", "?")
        # candidate if prunable, or non-primary with merged branch
        merged = False
        if branch:
            r = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", branch, base],
                capture_output=True,
                text=True,
            )
            merged = r.returncode == 0
            if merged and path != primary:
                flags.append("branch-merged-into-base")
        if not flags or flags == ["primary"]:
            continue
        found_wt = True
        when = last_commit_time(repo, head if head != "?" else (branch or "HEAD"))
        print(f"- path={path}")
        print(f"  branch={branch or '(detached)'} head={head[:12] if head!='?' else '?'} last_commit={when}")
        print(f"  flags={','.join(flags)}")
    if not found_wt:
        print("(none)")
    print()

    print("## merged local branches (not checked out as primary tip)")
    merged_out = run(repo, "branch", "--merged", base).splitlines()
    current = run(repo, "branch", "--show-current").strip()
    rows = []
    for line in merged_out:
        name = line.strip().lstrip("* ").strip()
        if not name or name == base:
            continue
        if name.startswith("("):
            continue
        when = last_commit_time(repo, name)
        rows.append((when, name, name == current))
    rows.sort()
    if not rows:
        print("(none)")
    else:
        for when, name, is_cur in rows:
            mark = " [current]" if is_cur else ""
            print(f"- {name}{mark} last_commit={when}")
    print()
    print("read-only: nothing was deleted.")


if __name__ == "__main__":
    main()
