#!/usr/bin/env python3
"""Delete every local clip that is not 4K. K's order (2026-11-23).

"ถ้าเหลือคลิปที่ยังไม่ใช่ 4k ลบทิ้งให้หมดเลย อย่าเอามาเก็บไว้อีก" -- anything
already uploaded may stay on YouTube, but a sub-4K file must not sit on disk
waiting to be uploaded by mistake.

    python3 scripts/purge_sub4k.py --dry-run     # say what would go
    python3 scripts/purge_sub4k.py               # delete it

A file is kept when it meets FOUR_K for its own orientation (a vertical Short is
4K at 2160x3840, a long-form at 3840x2160). An unreadable file is reported, not
silently deleted, so a half-written build cannot hide behind the sweep.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import upload_gate  # noqa: E402

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")
SKIP_DIR = ("/.git", "/node_modules", "/site-packages", "/__pycache__")
DEFAULT_ROOTS = ("work", "/tmp", os.path.expanduser("~/.cache/content-lab"))


def sweep(roots: list[str], dry_run: bool = False) -> dict:
    kept, gone, unreadable = [], [], []
    freed = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if any(s in dirpath for s in SKIP_DIR):
                continue
            for name in files:
                if not name.lower().endswith(VIDEO_EXT):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                w, h, _ = upload_gate.probe(path)
                if not w:
                    unreadable.append(path)
                    continue
                kind = "short" if h > w else "long"
                need_w, need_h = upload_gate.FOUR_K[kind]
                if w >= need_w and h >= need_h:
                    kept.append((path, w, h))
                    continue
                gone.append((path, w, h, size))
                freed += size
                if not dry_run:
                    os.remove(path)
    return {"kept": kept, "gone": gone, "unreadable": unreadable, "freed": freed}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=None,
                    help=f"where to look (default: {', '.join(DEFAULT_ROOTS)})")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when a sub-4K file is found (a check that can fail)")
    args = ap.parse_args()
    roots = [r if os.path.isabs(r) else os.path.join(ROOT, r) for r in (args.root or DEFAULT_ROOTS)]

    res = sweep(roots, args.dry_run)
    verb = "would delete" if args.dry_run else "deleted"
    for path, w, h, size in res["gone"]:
        print(f"{verb} {w}x{h} {size / 1e6:7.1f} MB  {path}")
    for path in res["unreadable"]:
        print(f"unreadable (kept)  {path}")
    print(f"\nkept 4K: {len(res['kept'])}  |  {verb}: {len(res['gone'])} "
          f"({res['freed'] / 1e6:.1f} MB)  |  unreadable: {len(res['unreadable'])}")
    if args.strict and (res["gone"] or res["unreadable"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
