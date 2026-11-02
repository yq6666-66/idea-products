#!/usr/bin/env python3
"""log-slimmer: report-only log size scanner (v1, changes nothing).

Usage:
    python3 log-slimmer.py <directory> [--top N] [--plan --older-than-days D]

Rules, from the user's own file hygiene:
- Read-only by default: it only lists files, never deletes or compresses.
- --plan only prints what *would* be archived (files older than D days);
  it still does not touch anything. Archiving itself is a later version
  and needs the user's explicit go-ahead, plus a backup first.
- Only scan directories the user owns; never point it at backups or
  unknown-origin files.
"""
import argparse
import os
import sys
from datetime import datetime, timezone


def scan(root):
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.lower().endswith(".log"):
                continue
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError as exc:
                print(f"skip (unreadable): {path} ({exc})", file=sys.stderr)
                continue
            found.append((path, st.st_size, st.st_mtime))
    return found


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    ap = argparse.ArgumentParser(description="Report-only log size scanner.")
    ap.add_argument("directory", help="Directory to scan for *.log files")
    ap.add_argument("--top", type=int, default=20, help="Show top N largest files")
    ap.add_argument("--plan", action="store_true",
                    help="Also print what would be archived (no action taken)")
    ap.add_argument("--older-than-days", type=int, default=30)
    args = ap.parse_args()

    if not os.path.isdir(args.directory):
        print(f"not a directory: {args.directory}", file=sys.stderr)
        return 2

    files = scan(args.directory)
    files.sort(key=lambda item: item[1], reverse=True)
    total = sum(size for _p, size, _m in files)
    print(f"directory: {args.directory}")
    print(f"log files: {len(files)}, total size: {human(total)}")
    print(f"top {args.top} largest:")
    for path, size, mtime in files[: args.top]:
        when = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"  {human(size):>10}  {when}  {path}")

    if args.plan:
        now = datetime.now(tz=timezone.utc).timestamp()
        cutoff = now - args.older_than_days * 86400
        old = [f for f in files if f[2] < cutoff]
        print(f"\nPLAN ONLY (nothing changed): {len(old)} file(s) older than "
              f"{args.older_than_days} days would be archived, not deleted:")
        for path, size, mtime in old:
            when = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
            print(f"  {human(size):>10}  {when}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
