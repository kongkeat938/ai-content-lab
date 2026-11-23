#!/usr/bin/env python3
"""K's upload rules must be able to REFUSE, not just be written down.

"ต้อง 4k เท่านั้นถึงอัพขึ้นได้ ห้ามซ้ำ ทั้งภาพ ดนตรี บท" (2026-11-23). A rule that
only ever says yes is decoration, so each case below is a real refusal the gate
has to make -- and one clean clip it has to let through.

    python3 scripts/test_upload_gate.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import upload_gate as ug

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def make_video(path: str, w: int, h: int) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"testsrc=size={w}x{h}:rate=10:duration=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", path],
                       stdin=subprocess.DEVNULL)
    return r.returncode == 0


GOOD = ("คืนนี้ลองวางมือบนท้องแล้วขอบคุณร่างกายที่แบกเรามาทั้งวัน "
        "ร่างกายนี้ทำงานให้เราโดยไม่เคยขอพัก เช้าถึงเย็นมันพาเราเดินพาเราหายใจ "
        "คืนนี้ลองวางมือลงบนหน้าท้องช้า ๆ บอกมันเบา ๆ ว่าขอบคุณที่อดทนมาทั้งวัน")
OTHER = ("วันนี้ฝนตกตั้งแต่เช้า ถนนเปียกจนต้องเดินช้า ๆ "
         "รถติดยาวกว่าทุกวัน แต่พอถึงบ้านก็ยังมีข้าวอุ่นรออยู่ "
         "บางวันการได้กลับบ้านก็เพียงพอแล้ว")


def main() -> int:
    tmp = tempfile.mkdtemp()
    ok1080 = make_video(os.path.join(tmp, "s1080.mp4"), 1080, 1920)
    ok4k = make_video(os.path.join(tmp, "s4k.mp4"), 2160, 3840)

    if ok1080 and ok4k:
        check(ug.resolution_problems(os.path.join(tmp, "s1080.mp4"), "short") != [],
              "a 1080x1920 Short is refused")
        check(ug.resolution_problems(os.path.join(tmp, "s4k.mp4"), "short") == [],
              "a 2160x3840 Short passes")
        check(ug.resolution_problems(os.path.join(tmp, "s4k.mp4"), "long") != [],
              "a vertical 4K file is not a long-form 4K file")
    else:
        print("skip  the resolution cases (no ffmpeg on PATH)")

    art = {"md5": {"aaaa1111": "126", "bbbb2222": "127"}}
    check(ug.image_problems(["aaaa1111"], art, sid="191") != [],
          "a picture already used by 126 is refused")
    check(ug.image_problems(["aaaa1111"], art, sid="126") == [],
          "a re-render of 126 may reuse its own picture")
    check(ug.image_problems(["cccc3333"], art, sid="191") == [], "a fresh picture passes")

    beds = {"beds": {"bed-calm.mp3": "126"}}
    check(ug.music_problems("bed-calm.mp3", beds, sid="191") != [],
          "a bed already under 126 is refused")
    check(ug.music_problems("bed-calm.mp3", beds, sid="126") == [],
          "a re-render of 126 may keep its own bed")
    check(ug.music_problems("bed-night.mp3", beds, sid="191") == [], "a fresh bed passes")

    check(ug.script_problems(GOOD, [("126", GOOD)]) != [], "the same script is refused")
    check(ug.script_problems(GOOD, [("127", OTHER)]) == [], "a different script passes")
    half = GOOD[: len(GOOD) // 2] + " แล้วก็นอนหลับให้สบาย"
    check(ug.script_problems(half, [("126", GOOD)]) != [], "a half-copied script is refused")

    ok, reasons = ug.check("short", None, md5s=["cccc3333"], art_ledger=art,
                           bed="bed-night.mp3", bed_ledger=beds, sid="191",
                           narration=OTHER, published=[("126", GOOD)])
    check(ok and not reasons, f"a clean clip passes ({reasons})")
    ok, reasons = ug.check("short", None, md5s=["aaaa1111"], art_ledger=art,
                           bed="bed-calm.mp3", bed_ledger=beds, sid="191",
                           narration=GOOD, published=[("126", GOOD)])
    check(not ok and len(reasons) == 3, f"all three repeats are named ({reasons})")

    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
