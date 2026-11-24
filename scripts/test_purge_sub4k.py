#!/usr/bin/env python3
"""The purge must delete the 1080p file and keep the 4K one -- both directions.

K (2026-11-23): "ถ้าเหลือคลิปที่ยังไม่ใช่ 4k ลบทิ้งให้หมดเลย". A sweep that keeps
everything would look identical to a working one, so this test builds both sizes
and checks which one survives.

    python3 scripts/test_purge_sub4k.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import purge_sub4k  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def make(path: str, w: int, h: int) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"testsrc=size={w}x{h}:rate=5:duration=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", path],
                       stdin=subprocess.DEVNULL)
    return r.returncode == 0


def main() -> int:
    tmp = tempfile.mkdtemp()
    small_short = os.path.join(tmp, "small_short.mp4")
    big_short = os.path.join(tmp, "big_short.mp4")
    small_long = os.path.join(tmp, "small_long.mp4")
    big_long = os.path.join(tmp, "big_long.mp4")
    if not all(make(p, w, h) for p, w, h in ((small_short, 1080, 1920), (big_short, 2160, 3840),
                                              (small_long, 1920, 1080), (big_long, 3840, 2160))):
        print("skip  (no ffmpeg on PATH)")
        return 0

    dry = purge_sub4k.sweep([tmp], dry_run=True)
    check(len(dry["gone"]) == 2 and len(dry["kept"]) == 2,
          f"dry run finds 2 to delete and 2 to keep ({len(dry['gone'])}/{len(dry['kept'])})")
    check(os.path.exists(small_short) and os.path.exists(small_long), "dry run deletes nothing")

    res = purge_sub4k.sweep([tmp])
    check(len(res["gone"]) == 2, f"the sweep deleted 2 ({len(res['gone'])})")
    check(not os.path.exists(small_short) and not os.path.exists(small_long),
          "the 1080p files are gone")
    check(os.path.exists(big_short) and os.path.exists(big_long), "the 4K files are kept")

    dead = os.path.join(tmp, "dead_build")
    alive = os.path.join(tmp, "live_build")
    os.makedirs(dead, exist_ok=True)
    os.makedirs(alive, exist_ok=True)
    make(os.path.join(dead, "clip.mp4"), 1920, 1080)
    open(os.path.join(dead, "bed.wav"), "wb").write(b"RIFF" * 1000)
    make(os.path.join(alive, "clip.mp4"), 3840, 2160)
    open(os.path.join(alive, "bed.wav"), "wb").write(b"RIFF" * 1000)
    gone = purge_sub4k.sweep_dirs(tmp, dry_run=True)
    check(len(gone) == 1 and gone[0][0].endswith("dead_build"),
          f"a build dir with no 4K clip is dead weight ({[g[0] for g in gone]})")
    purge_sub4k.sweep_dirs(tmp)
    check(not os.path.isdir(dead), "the dead build dir is removed (audio and all)")
    check(os.path.isdir(alive), "a build dir that holds a 4K clip is kept")

    blind = subprocess.run([sys.executable, os.path.join(HERE, "purge_sub4k.py"), "--dry-run",
                            "--root", alive], capture_output=True, text=True,
                           env={"PATH": "/nonexistent", "HOME": os.environ.get("HOME", "/tmp")},
                           stdin=subprocess.DEVNULL)
    check(blind.returncode == 2 and "BLIND" in (blind.stdout + blind.stderr),
          f"without ffprobe it refuses to run (exit {blind.returncode})")

    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
