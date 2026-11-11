#!/usr/bin/env python3
"""The channel audit must flag a video that no manifest records.

The pace, cap and gap guards only see uploads the rails made. A video that
appears on the channel but in no manifest came from something else (a manual
Studio upload, or a second tool) and is invisible to all of them. Measured
2026-11-11: ch4 had 97 uploads against 57 recorded, and 25 titles carried a
brand token ("เรื่องเล่าการ์ตูน") no code in this repo writes.

This guard must be able to FAIL: it fails if find_defects stops naming an
unrecorded video, or stops naming the old brand.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_channels as ac  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def vid(vid_id: str, title: str) -> dict:
    return {"id": vid_id,
            "snippet": {"title": title, "description": "ดูต่อ youtube.com/@x",
                        "tags": ["t"]}}


def main() -> int:
    ch = {"description": "d", "keywords": "k", "default_language": "th",
          "country": "TH", "videos": "10"}

    # A recorded video, an unrecorded one, and an unrecorded one on the old brand.
    vids = [vid("REC1", "เรื่องที่บันทึกไว้แล้ว #Shorts"),
            vid("ROGUE1", "เรื่องที่ไม่มีใน manifest #Shorts"),
            vid("ROGUE2", f"เรื่องเก่า {ac.OLD_BRAND} #Shorts")]
    recorded = {"REC1"}

    d = ac.find_defects(ch, [{"id": "PL"}], vids, recorded)
    joined = "\n".join(d)

    if "REC1" in joined:
        fail("a recorded video was wrongly flagged as unrecorded")
    if "ROGUE1" not in joined:
        fail("an unrecorded video was NOT flagged; the audit is blind to a "
             "second uploader")
    if "ROGUE2" not in joined or ac.OLD_BRAND not in joined:
        fail("an old-brand title was NOT flagged")

    # And the guard can FAIL: with no recorded set, nothing is unrecorded.
    d2 = ac.find_defects(ch, [{"id": "PL"}], vids, None)
    if any("in NO manifest" in x for x in d2):
        fail("with recorded=None the audit should not invent an unrecorded flag")

    print("OK: the audit names an unrecorded video and an old-brand title")
    return 0


if __name__ == "__main__":
    sys.exit(main())
