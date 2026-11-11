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

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_channels as ac  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def vid(vid_id: str, title: str, published: str = "2020-01-01T00:00:00Z") -> dict:
    return {"id": vid_id,
            "snippet": {"title": title, "description": "ดูต่อ youtube.com/@x",
                        "tags": ["t"], "publishedAt": published}}


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

    # The live rogue stream and the pre-manifest backlog must be told apart:
    # a recent unrecorded upload is the stream that is still running; an old one
    # is history. A take-down acts on the former, never the latter.
    recent = "2026-11-11T00:00:00Z"
    old = "2026-01-01T00:00:00Z"
    d3 = "\n".join(ac.find_defects(ch, [{"id": "PL"}],
                                   [vid("LIVE", "สด #Shorts", recent),
                                    vid("OLD", "เก่า #Shorts", old)], set()))
    if "LIVE rogue upload" not in d3:
        fail("a recent unrecorded upload was NOT named as the live rogue stream")
    if "historical, pre-manifest" not in d3:
        fail("an old unrecorded upload was NOT marked historical; a take-down "
             "would hide legitimate old videos")

    # And the guard can FAIL: with no recorded set, nothing is unrecorded.
    d2 = ac.find_defects(ch, [{"id": "PL"}], vids, None)
    if any("in NO manifest" in x for x in d2):
        fail("with recorded=None the audit should not invent an unrecorded flag")

    # The detection is worthless if the alert cannot be seen. Measured
    # 2026-11-11: the step summary is not where K looks; the alert must be a
    # GitHub issue (like health.py), so account-watch must actually invoke the
    # audit with --alert and hold issues:write. Match the command line, not a
    # bare substring (a comment mentions --alert, which would mask a regression).
    wf = open(str(Path(__file__).resolve().parents[1]
                  / ".github" / "workflows" / "account-watch.yml"),
              encoding="utf-8").read()
    if not re.search(r"audit_channels\.py[^\n]*--alert", wf):
        fail("account-watch no longer runs `audit_channels.py ... --alert`; a live "
             "rogue upload would be measured but never reach anyone")
    if "issues: write" not in wf:
        fail("account-watch lacks issues:write; the rogue-upload alert cannot open")

    print("OK: the audit names an unrecorded video, an old-brand title, splits "
          "the live rogue stream from the historical backlog, and the alert is wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
