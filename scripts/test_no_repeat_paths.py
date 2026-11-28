#!/usr/bin/env python3
"""K (2026-11-23): new work keeps coming, and the old must never come back --
"ของเก่าห้ามเอามาทำซ้ำนะ ย้ำอย่าลืมทั้งภาพ บทแต่งด้วย".

This holds the three paths that could let a repeat through:

  1. the art ledger the build writes (a picture belongs to one video);
  2. the bed ledger (name AND content);
  3. the script ledger + the long-form upload gate + the writers' room, which
     must refuse a story that is half of one already out.

    python3 scripts/test_no_repeat_paths.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import publish_youtube  # noqa: E402
import upload_gate  # noqa: E402
import shorts_draft_gate  # noqa: E402

failures: list[str] = []
SCRIPT_A = ("คืนนี้ลองนึกถึงเรื่องดีๆ สักเรื่องก่อนนอน ใจของคนเรามักจำเรื่องร้ายไว้แน่น "
            "แต่เรื่องดีๆ มักถูกเก็บไว้ในมุมที่ลึกกว่า ลองเอามันออกมาวางตรงหน้าเบาๆ "
            "แล้วปล่อยให้ลมหายใจพัดมันไปช้าๆ คืนนี้ไม่ต้องคิดอะไรให้มาก")
SCRIPT_B = ("ยายบัวจุดตะเกียงไว้ทุกคืน ไม่ได้รอใคร แต่รอคนที่ยังหลงทาง ไฟดวงเล็กส่องทาง "
            "ให้คนเดินผ่าน บางคืนมีคนนั่งลงข้างตะเกียง เล่าเรื่องเก่าให้ฟังจนดึก "
            "แล้วจากไปโดยไม่บอกชื่อ")


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def make_video(path: str, w: int = 3840, h: int = 2160) -> bool:
    return subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                           "-i", f"testsrc=size={w}x{h}:rate=5:duration=1",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", path],
                          stdin=subprocess.DEVNULL).returncode == 0


def main() -> int:
    tmp = tempfile.mkdtemp()
    art = os.path.join(tmp, "art.json")

    print("a picture belongs to one video")
    check(upload_gate.record_art(art, ["aaa"], "story_01") == [], "the first claim is clean")
    check(bool(upload_gate.record_art(art, ["aaa"], "story_02")),
          "the same picture for another story is refused")
    check(upload_gate.record_art(art, ["aaa"], "story_01") == [],
          "a re-render of the same story may reuse its own picture")

    print("a bed is claimed by name and by content")
    beds = os.path.join(tmp, "beds.json")
    check(upload_gate.record_bed(beds, "calm.wav", "story_01") == [], "the first bed is clean")
    check(bool(upload_gate.record_bed(beds, "calm.wav", "story_02")), "the same bed is refused")
    check(upload_gate.record_art(beds, ["bbb"], "story_03") == [], "a fresh bed is claimed")
    check(bool(upload_gate.record_art(beds, ["bbb"], "story_04")),
          "the same bed copied under a new name is refused")
    check(upload_gate.record_art(beds, ["bbb"], "story_03") == [], "re-recording is idempotent")

    print("a script is claimed once")
    scripts = os.path.join(tmp, "scripts.json")
    check(upload_gate.record_script(scripts, "story_01", SCRIPT_A) == [], "the first script is clean")
    check(bool(upload_gate.record_script(scripts, "story_02", SCRIPT_A)),
          "the same story told again is refused")
    check(upload_gate.record_script(scripts, "story_03", SCRIPT_B) == [],
          "a genuinely new story passes")
    check(len(upload_gate.published_texts(scripts)) == 2, "the ledger keeps both published scripts")

    print("the long-form uploader refuses what the ledger already heard")
    video = os.path.join(tmp, "v.mp4")
    if make_video(video):
        ok, why = publish_youtube.freshness("t", video, SCRIPT_B, "story_04", ledger_path=scripts)
        check(not ok and any("same as" in w for w in why), f"a repeat is refused ({why})")
        ok, why = publish_youtube.freshness("t", video, "ตะเกียงดวงสุดท้ายยังคงสว่างอยู่ทุกคืน "
                                            "รอคนที่เดินผ่านมาแล้วนั่งลงเล่าเรื่องราวของตัวเอง",
                                            "story_05", ledger_path=scripts)
        check(ok, f"a new script on a 4K file passes ({why})")
        low = os.path.join(tmp, "low.mp4")
        if make_video(low, 1920, 1080):
            ok, why = publish_youtube.freshness("t", low, "เรื่องใหม่ที่ไม่เคยเล่าที่ไหนมาก่อน",
                                                "story_06", ledger_path=scripts)
            check(not ok and any("not 4K" in w for w in why), f"1080p is still refused ({why})")
    else:
        print("skip  (no ffmpeg on PATH)")

    print("the writers' room refuses a half-copied draft")
    draft = {"hook": SCRIPT_A[:40], "lines": SCRIPT_A[40:].split(" ")[:6], "cta": "ฝากกดติดตาม"}
    bad = shorts_draft_gate.problems(draft, [], [SCRIPT_A])
    check(any("same as a published one" in b for b in bad), f"a copy is caught ({bad})")
    fresh = {"hook": "ยายบัวจุดตะเกียงรอคนหลงทาง", "lines": SCRIPT_B[20:].split(" ")[:6],
             "cta": "ฝากกดติดตาม"}
    check(not any("same as a published one" in b for b in shorts_draft_gate.problems(fresh, [], [SCRIPT_A])),
          "a new draft is not flagged as a copy")

    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
