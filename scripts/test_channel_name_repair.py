#!/usr/bin/env python3
"""The branding repair must trigger on a STALE description, not just a missing one.

Measured 2026-11-16: ch4's live blurb was still the pre-pivot family text after the
genre moved to knowledge. `set_channel_name.run` gated the write with a truthiness
check (`not chb.get("description")`), so a non-empty-but-wrong description looked
"done" and the rail skipped the repair forever.

This drives the real `run()` decision path (stubbing only the HTTP boundary:
`access_token` and `api`) and asserts the branch taken. It FAILS on the old
truthiness gate: a stale description then reads as "already ... skip".
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("set_channel_name",
                                              ROOT / "scripts" / "set_channel_name.py")
scn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scn)

T = scn.TARGET["kongkeat-story"]
OLD_DESC = "เรื่องเล่าความทรงจำครอบครัวไทย — พ่อ แม่ พี่ ยาย ตา"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def make_item(desc: str, keywords: str, loc_title: str) -> dict:
    return {
        "id": "UC7gCIu4G_7QCEJ8hJ-34zoQ",
        "snippet": {"title": "เรื่องเล่าอบอุ่นใจ"},
        "brandingSettings": {"channel": {
            "title": "เรื่องเล่าอบอุ่นใจ",
            "description": desc,
            "keywords": keywords,
            "defaultLanguage": "th",
        }},
        "localizations": {"th_TH": {"title": loc_title}},
    }


def decide(item: dict) -> str:
    scn.access_token = lambda env: "tok"                      # no network
    # The GET path reads ["items"][0]; any PUT path reads the item fields back.
    scn.api = lambda tok, method, url, body=None: {**item, "items": [item]}
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = scn.run("kongkeat-story", dry=True, verify_only=False)
    if rc != 0:
        fail(f"dry-run returned {rc}, expected 0")
    return buf.getvalue()


def main() -> int:
    # 1. Stale description + stale keywords -> MUST plan a repair.
    out = decide(make_item(OLD_DESC, "เรื่องเล่า,ครอบครัว", T["title"]))
    if "restoring them" not in out:
        fail("a stale (non-empty, wrong) description did NOT trigger a repair -- "
             "the gate is still a truthiness check:\n" + out)
    if "already renamed and branded -- skip" in out:
        fail("a stale description was read as 'already branded' -- the exact bug:\n" + out)

    # 2. Only the keywords are stale -> MUST also plan a repair.
    out = decide(make_item(T["description"], "เก่า,ผิด", T["title"]))
    if "restoring them" not in out:
        fail("stale keywords alone did not trigger a repair:\n" + out)

    # 3. Everything matches the target -> MUST skip (no needless 50-unit write).
    out = decide(make_item(T["description"], T["keywords"], T["title"]))
    if "already renamed and branded -- skip" not in out:
        fail("a channel already on target was not skipped:\n" + out)

    print("OK: a stale description/keywords triggers a repair; an on-target "
          "channel is skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
