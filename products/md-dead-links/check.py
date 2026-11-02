#!/usr/bin/env python3
"""Scan Markdown for broken local and HTTP(S) links. Read-only."""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
ANGLE_RE = re.compile(r"<(https?://[^>]+)>")
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")


def extract_links(text: str) -> list[str]:
    links = LINK_RE.findall(text) + ANGLE_RE.findall(text)
    out = []
    for raw in links:
        url = raw.strip()
        if url.startswith("#") or url.startswith("?"):
            continue
        if any(url.lower().startswith(s) for s in SKIP_SCHEMES):
            continue
        # drop anchors for local path existence; keep full for http
        out.append(url)
    return out


def check_local(repo: Path, md_file: Path, url: str) -> tuple[str, str]:
    path_part = url.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return "ok", "same-doc-anchor"
    target = (md_file.parent / path_part).resolve()
    try:
        target.relative_to(repo.resolve())
    except ValueError:
        # allow absolute within repo via resolve failure outside — still check exists
        pass
    if target.exists():
        return "ok", "exists"
    return "dead", "missing-file"


def check_http(url: str, timeout: float) -> tuple[str, str]:
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "md-dead-links/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                if 200 <= int(code) < 400:
                    return "ok", f"{method}:{code}"
                if int(code) in (405, 501) and method == "HEAD":
                    continue
                return "dead", f"{method}:{code}"
        except urllib.error.HTTPError as e:
            if e.code in (405, 501) and method == "HEAD":
                continue
            return "dead", f"HTTPError:{e.code}"
        except TimeoutError:
            return "timeout", "TimeoutError"
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            if "timed out" in str(e).lower() or name == "TimeoutError":
                return "timeout", name
            if method == "HEAD":
                continue
            return "dead", name
    return "dead", "unreachable"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument(
        "--warn-only",
        action="store_true",
        help="print broken links but always exit 0 (default: exit 1 if any broken)",
    )
    args = ap.parse_args()
    repo = args.repo.resolve()
    md_files = [p for p in repo.rglob("*.md") if ".git" not in p.parts]
    print("# md-dead-links")
    print(f"repo: {repo}")
    print(f"files: {len(md_files)}")
    print(f"generated_at: {datetime.now(timezone.utc).isoformat()}")
    print()

    jobs = []
    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        for url in extract_links(text):
            jobs.append((md, url))

    broken = []
    http_jobs = []
    for md, url in jobs:
        if url.startswith("http://") or url.startswith("https://"):
            http_jobs.append((md, url))
        else:
            status, detail = check_local(repo, md, url)
            if status != "ok":
                broken.append((status, md, url, detail))

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futs = {ex.submit(check_http, url, args.timeout): (md, url) for md, url in http_jobs}
        for fut in as_completed(futs):
            md, url = futs[fut]
            status, detail = fut.result()
            if status != "ok":
                broken.append((status, md, url, detail))

    if not broken:
        print("no broken links found.")
        return
    print("## broken")
    for status, md, url, detail in sorted(broken, key=lambda x: (x[0], str(x[1]), x[2])):
        rel = md.relative_to(repo)
        print(f"- [{status}] {rel}: {url} ({detail})")
    if not args.warn_only:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
