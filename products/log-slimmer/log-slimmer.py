#!/usr/bin/env python3
"""log-slimmer: log size report, with optional backup-first archive (v2).

Usage:
    python3 log-slimmer.py <directory> [--top N] [--plan --older-than-days D]
    python3 log-slimmer.py <directory> --archive --backup-dir <dir> \
        --archive-dir <dir> --confirm-archive [--older-than-days D]

Rules, from the user's own file hygiene:
- Default is read-only: it only lists files, never deletes or compresses.
- --plan only prints what *would* be archived (files older than D days).
- --archive is opt-in and gated: it refuses without --backup-dir,
  --archive-dir and --confirm-archive. For each old file it first copies
  the original byte-for-byte to the backup dir, then writes a .gz copy
  to the archive dir. It never deletes or overwrites the original.
- Backup and archive dirs must be outside the scanned directory, and
  must not be the scanned directory itself; otherwise it refuses.
- Only scan directories the user owns; never point it at backups or
  unknown-origin files.
"""
import argparse
import gzip
import os
import shutil
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


def _is_outside(child, parent):
    child = os.path.abspath(child)
    parent = os.path.abspath(parent)
    return child != parent and not child.startswith(parent + os.sep)


def main():
    ap = argparse.ArgumentParser(description="Log size report, optional backup-first archive.")
    ap.add_argument("directory", help="Directory to scan for *.log files")
    ap.add_argument("--top", type=int, default=20, help="Show top N largest files")
    ap.add_argument("--plan", action="store_true",
                    help="Also print what would be archived (no action taken)")
    ap.add_argument("--older-than-days", type=int, default=30)
    ap.add_argument("--archive", action="store_true",
                    help="Archive old files (requires --backup-dir, --archive-dir, --confirm-archive)")
    ap.add_argument("--backup-dir", default=None, help="Where to copy originals first")
    ap.add_argument("--archive-dir", default=None, help="Where to write .gz copies")
    ap.add_argument("--confirm-archive", action="store_true",
                    help="Explicit confirmation for --archive; without it, only the plan is printed")
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

    now = datetime.now(tz=timezone.utc).timestamp()
    cutoff = now - args.older_than_days * 86400
    old = [f for f in files if f[2] < cutoff]

    if args.plan or args.archive:
        print(f"\nPLAN: {len(old)} file(s) older than "
              f"{args.older_than_days} days would be archived, not deleted:")
        for path, size, mtime in old:
            when = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
            print(f"  {human(size):>10}  {when}  {path}")

    if not args.archive:
        return 0
    if not args.backup_dir or not args.archive_dir or not args.confirm_archive:
        print("archive refused: pass --backup-dir, --archive-dir and "
              "--confirm-archive together; nothing was changed.", file=sys.stderr)
        return 2
    root = os.path.abspath(args.directory)
    for dest, label in ((args.backup_dir, "backup"), (args.archive_dir, "archive")):
        if not _is_outside(dest, root):
            print(f"archive refused: {label} dir must be outside the scanned "
                  f"directory; nothing was changed.", file=sys.stderr)
            return 2
    for path, size, mtime in old:
        rel = os.path.relpath(path, root)
        backup_path = os.path.join(args.backup_dir, rel)
        archive_path = os.path.join(args.archive_dir, rel + ".gz")
        os.makedirs(os.path.dirname(backup_path) or ".", exist_ok=True)
        os.makedirs(os.path.dirname(archive_path) or ".", exist_ok=True)
        shutil.copy2(path, backup_path)
        with open(path, "rb") as src, gzip.open(archive_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        gz_size = os.path.getsize(archive_path)
        print(f"  archived: {path} -> backup {backup_path} "
              f"({human(size)}), archive {archive_path} ({human(gz_size)}); "
              f"original left untouched")
    print(f"archive done: {len(old)} file(s); originals were not deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
