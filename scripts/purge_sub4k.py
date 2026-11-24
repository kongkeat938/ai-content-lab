#!/usr/bin/env python3
"""Delete everything on this machine that is not 4K. K's order (2026-11-23).

"ของที่ไม่ใช่ 4k ลบทิ้งให้หมด จะได้ไม่หนักเครื่องเราด้วย" -- a clip already on
YouTube may stay there, but a sub-4K file, and any build directory that holds no
4K clip at all (audio beds, frames, 1080p segments), must not sit on the disk.

    python3 scripts/purge_sub4k.py --dry-run --dirs    # say what would go
    python3 scripts/purge_sub4k.py --dirs              # delete it

A file is kept when it meets FOUR_K for its own orientation (a vertical Short is
4K at 2160x3840, a long-form at 3840x2160). If ffprobe is not on PATH the sweep
refuses to run and exits 2 -- measuring nothing must never look like finding
nothing (the trap in topics/05).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import upload_gate  # noqa: E402

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")
SKIP_DIR = ("/.git", "/node_modules", "/site-packages", "/__pycache__")
DEFAULT_ROOTS = ("work", "/tmp", os.path.expanduser("~/.cache/content-lab"))
BLIND = 2


def have_ffprobe() -> bool:
    return shutil.which("ffprobe") is not None


def is_4k(path: str) -> tuple[bool, tuple[int, int]]:
    w, h, _ = upload_gate.probe(path)
    if not w:
        return False, (0, 0)
    kind = "short" if h > w else "long"
    need_w, need_h = upload_gate.FOUR_K[kind]
    return w >= need_w and h >= need_h, (w, h)


def videos(root: str):
    for dirpath, _dirs, files in os.walk(root):
        if any(s in dirpath for s in SKIP_DIR):
            continue
        for name in files:
            if name.lower().endswith(VIDEO_EXT):
                yield os.path.join(dirpath, name)


def sweep(roots: list[str], dry_run: bool = False) -> dict:
    kept, gone, unreadable = [], [], []
    freed = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for path in videos(root):
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            ok, dims = is_4k(path)
            if not dims[0]:
                unreadable.append(path)
                continue
            if ok:
                kept.append((path, *dims))
                continue
            gone.append((path, *dims, size))
            freed += size
            if not dry_run:
                os.remove(path)
    return {"kept": kept, "gone": gone, "unreadable": unreadable, "freed": freed}


def dir_size(path: str) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


def sweep_dirs(root: str, dry_run: bool = False) -> list[tuple[str, int, int]]:
    """Remove each immediate subdirectory of `root` that holds no 4K clip."""
    dead = []
    if not os.path.isdir(root):
        return dead
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        clips = list(videos(path))
        if any(is_4k(c)[0] for c in clips):
            continue
        dead.append((path, dir_size(path), len(clips)))
        if not dry_run:
            shutil.rmtree(path)
    return dead


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=None,
                    help=f"where to look (default: {', '.join(DEFAULT_ROOTS)})")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dirs", action="store_true",
                    help="also delete build dirs under work/ that hold no 4K clip")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when a sub-4K file is found (a check that can fail)")
    args = ap.parse_args()

    if not have_ffprobe():
        print("BLIND: ffprobe is not on PATH -- nothing measured, nothing deleted",
              file=sys.stderr)
        return BLIND

    roots = [r if os.path.isabs(r) else os.path.join(ROOT, r) for r in (args.root or DEFAULT_ROOTS)]
    res = sweep(roots, args.dry_run)
    verb = "would delete" if args.dry_run else "deleted"
    for path, w, h, size in res["gone"]:
        print(f"{verb} {w}x{h} {size / 1e6:7.1f} MB  {path}")
    for path in res["unreadable"]:
        print(f"unreadable (kept)  {path}")
    print(f"\nkept 4K: {len(res['kept'])}  |  {verb}: {len(res['gone'])} "
          f"({res['freed'] / 1e6:.1f} MB)  |  unreadable: {len(res['unreadable'])}")

    if args.dirs:
        dead = sweep_dirs(os.path.join(ROOT, "work"), args.dry_run)
        for path, size, clips in dead:
            print(f"{'would remove dir' if args.dry_run else 'removed dir'} "
                  f"{size / 1e6:8.1f} MB  {clips} clip(s), none 4K  {path}")
        print(f"dirs {'to remove' if args.dry_run else 'removed'}: {len(dead)} "
              f"({sum(d[1] for d in dead) / 1e6:.1f} MB)")

    if args.strict and (res["gone"] or res["unreadable"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
