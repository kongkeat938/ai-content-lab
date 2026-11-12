#!/usr/bin/env python3
"""Guard the QA/critic gate: it must veto, not just accept.

A gate that only grades good builds proves nothing -- the old rail shipped the
single static card that held 5.2% AVD and every check it had passed it. So this
test feeds the gate the exact shape that shipped, plus a good one, and asserts the
gate tells them apart and that the veto reaches the manifest writer.

    python3 scripts/test_qa_gate.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import qa_gate  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def good_receipt() -> dict:
    # What the fixed rail produces: a hook, 17 cards, ~26 min, TV range, TP -3.2.
    return {
        "verdict": "pass",
        "audio_info": {"hook": {"name": "00_hook", "duration_sec": 11.0}},
        "video_info": {
            "duration_sec": 1580.71,
            "chapters": 17,
            "chapter_seconds": [10.67] + [90.0] * 16,
            "true_peak_dbfs": -3.2,
        },
    }


def old_static_receipt() -> dict:
    # What the rail used to ship: one static card for two hours, no hook. This is
    # the shape the gate exists to stop.
    return {
        "verdict": "pass",
        "audio_info": {},
        "video_info": {
            "duration_sec": 7246.8,
            "chapters": 1,
            "chapter_seconds": [7246.8],
            "true_peak_dbfs": -3.1,
        },
    }


def main() -> int:
    g = qa_gate.grade(good_receipt())
    if g["blocked"] or g["grade"] not in ("A", "B"):
        fail(f"a good build was blocked or downgraded: {g}")

    b = qa_gate.grade(old_static_receipt())
    if not b["blocked"]:
        fail("the old one-static-card shape was NOT vetoed; the gate is toothless")
    if not any("card" in r for r in b["reasons"]):
        fail(f"the veto did not name the static card: {b['reasons']}")
    if not any("hook" in r for r in b["reasons"]):
        fail(f"the veto did not name the missing hook: {b['reasons']}")

    # A malformed file must never be publishable, whatever else is right.
    broken = good_receipt()
    broken["verdict"] = "fail"
    if not qa_gate.grade(broken)["blocked"]:
        fail("a failed verifier was not vetoed")

    # A single card that is short is still a static picture -- veto.
    short_static = {
        "verdict": "pass",
        "audio_info": {"hook": {"duration_sec": 10.0}},
        "video_info": {"duration_sec": 600.0, "chapters": 1,
                       "chapter_seconds": [600.0], "true_peak_dbfs": -4.0},
    }
    if not qa_gate.grade(short_static)["blocked"]:
        fail("a single-card 10-minute file was not vetoed")

    # A card that holds too long is the static trap even when there are several.
    long_card = {
        "verdict": "pass",
        "audio_info": {"hook": {"duration_sec": 10.0}},
        "video_info": {"duration_sec": 3600.0, "chapters": 3,
                       "chapter_seconds": [1200.0, 1200.0, 1200.0],
                       "true_peak_dbfs": -4.0},
    }
    if not qa_gate.grade(long_card)["blocked"]:
        fail("a 20-minute card was not vetoed as static")

    # The night rail's intended format: 120 min, a short hook, many cards. This
    # must be publishable -- the old 90-min ceiling vetoed every such build.
    night = {
        "verdict": "pass",
        "audio_info": {"hook": {"duration_sec": 19.0}},
        "video_info": {"duration_sec": 7228.75, "chapters": 27,
                       "chapter_seconds": [258.0] * 27, "true_peak_dbfs": -3.1},
    }
    ng = qa_gate.grade(night)
    if ng["blocked"]:
        fail(f"the intended 120-minute night build was vetoed: {ng['reasons']}")
    # ...and it must not be *warned* either: a 120-min sleep file is the intended
    # format, so flagging every one of them (grade B forever) is a false alarm.
    if any("min" in w and "outside" in w for w in ng["warnings"]):
        fail(f"the intended 120-minute night build drew a length false alarm: {ng['warnings']}")

    # The length check must sweep the source, not hardcode one band: every band the
    # gate declares must be accepted, and a length just outside a band must warn.
    for lo, hi in qa_gate.LEN_OK_BANDS:
        for dur in (lo, (lo + hi) / 2, hi):
            r = dict(good_receipt())
            r["video_info"] = dict(r["video_info"], duration_sec=dur,
                                   chapter_seconds=[min(90.0, dur)] * max(2, int(dur // 90)))
            g2 = qa_gate.grade(r)
            if any("outside the" in w for w in g2["warnings"]):
                fail(f"a length inside a declared band ({dur/60:.1f} min) was warned: "
                     f"{g2['warnings']}")

    # ...and a length outside every band still warns, so the check is not vacuous.
    between = dict(good_receipt())
    between["video_info"] = dict(between["video_info"], duration_sec=60 * 60,
                                 chapter_seconds=[300.0] * 12)
    if not any("outside the" in w for w in qa_gate.grade(between)["warnings"]):
        fail("a 60-minute file (outside every intended band) drew no length warning")

    # But a file nothing like the format (200 min) is still vetoed.
    absurd = {
        "verdict": "pass",
        "audio_info": {"hook": {"duration_sec": 19.0}},
        "video_info": {"duration_sec": 200 * 60, "chapters": 27,
                       "chapter_seconds": [444.0] * 27, "true_peak_dbfs": -3.1},
    }
    if not qa_gate.grade(absurd)["blocked"]:
        fail("a 200-minute file was not vetoed as far from any usable format")

    # And the veto must reach the manifest writer, not just the grader.
    writer = open(os.path.join(HERE, "add_release_to_manifest.py"), encoding="utf-8").read()
    if 'state"] = "blocked"' not in writer:
        fail("add_release_to_manifest no longer marks a vetoed build as blocked")
    pub = open(os.path.join(HERE, "publish_batch.py"), encoding="utf-8").read()
    if '!= "blocked"' not in pub:
        fail("publish_batch no longer refuses a blocked entry")

    print("OK: the gate vetoes a static card / missing hook / failed verify and "
          "passes a chaptered build; the veto reaches the manifest and publish rails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
