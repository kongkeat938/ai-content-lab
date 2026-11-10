#!/usr/bin/env python3
"""Guard K's posting loop (2026-11-09): one clip, wait 2-3 h, read the result,
then keep a shape that worked or change one that did not.

The rail already had a *cap* (a daily ceiling) and a *gap* (MIN_GAP_HOURS), but a
cap only counts posts -- it never reads how they did, so nothing connected "this
clip flopped" to "the next clip should be different". That missing link is what
this loop adds, in scripts/pace.py, and this test locks it so a later edit cannot
quietly go back to posting on a timer with no feedback.

    python3 scripts/test_pace.py     # exit 0 = the loop is intact
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pace  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def _write_manifest(entries: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"shorts": entries}, fh)
    return path


def test_gap() -> None:
    if pace.MIN_GAP_HOURS < 2.0:
        fail(f"MIN_GAP_HOURS {pace.MIN_GAP_HOURS} is below K's 2-3 h window")
    # A post 1 h ago must be refused; one 3 h ago must be allowed.
    recent = _write_manifest({"01": {"video_id": "a", "posted_at": _iso(1.0)}})
    r = pace.gate("dharma", recent, token=None)
    if r["allowed"]:
        fail("gate allowed a post only 1 h after the last one")
    old = _write_manifest({"01": {"video_id": "a", "posted_at": _iso(3.0)}})
    r2 = pace.gate("dharma", old, token=None)
    if not r2["allowed"]:
        fail("gate refused a post 3 h after the last one (the window is 2-3 h)")
    os.unlink(recent)
    os.unlink(old)
    print("  gap: 1 h refused, 3 h allowed")


def test_order() -> None:
    cues = ("ลอง", "คืนนี้", "เปิดทิ้งไว้")
    cue = {"id": "c", "hook": "คืนนี้ลองทำแบบนี้"}
    plain = {"id": "p", "hook": "สมองไม่ยอมหยุดคิดเรื่องแย่ ๆ"}
    if pace.hook_shape(cue, cues) != "cue" or pace.hook_shape(plain, cues) != "plain":
        fail("hook_shape misclassifies the two shapes")
    # good/unknown -> the winning (cue) shape leads.
    if pace.order([plain, cue], cues, "good", "cue")[0] is not cue:
        fail("a good post did not keep the winning shape at the front")
    # bad -> the *other* shape leads, so the next clip is a change.
    if pace.order([plain, cue], cues, "bad", "cue")[0] is not plain:
        fail("a bad post did not switch to the other shape")
    if pace.order([cue, plain], cues, "bad", "plain")[0] is not cue:
        fail("a bad plain post did not switch to the cue shape")
    print("  order: good keeps, bad flips")


def test_grade() -> None:
    # Below the baseline clip count the verdict must be unknown, never invented.
    if pace.grade(999, 1.0, pace.MIN_BASELINE_CLIPS - 1) != "unknown":
        fail("graded with too few baseline clips; the verdict would be noise")
    if pace.grade(5.0, 2.0, 5) != "good" or pace.grade(1.0, 2.0, 5) != "bad":
        fail("grade did not split at the channel median")
    print("  grade: unknown below baseline, splits at the top-quarter bar")


def test_gate_end_to_end() -> None:
    """Prove gate() returns good/bad from real view counts, not just the gap.

    The view source is stubbed (no network in a guard test), but the arithmetic,
    the baseline, and the verdict are the real code path.
    """
    # Last post 3 h old; three old clips form the baseline at ~10 views/hour.
    entries = {
        "01": {"video_id": "old1", "posted_at": _iso(48)},
        "02": {"video_id": "old2", "posted_at": _iso(40)},
        "03": {"video_id": "old3", "posted_at": _iso(30)},
        "04": {"video_id": "last", "posted_at": _iso(3.0)},
    }
    scripts = [{"id": "01", "video_id": "old1", "hook": "คืนนี้ลองทำแบบนี้"},
               {"id": "04", "video_id": "last", "hook": "คืนนี้ลองทำแบบนี้"}]

    def fake_stats(_tok, _ids):
        return {"old1": {"views": 480, "published_at": None},
                "old2": {"views": 400, "published_at": None},
                "old3": {"views": 300, "published_at": None},
                "last": {"views": 300, "published_at": None}}   # 100/h >> baseline

    orig_stats, orig_av = pace.stats, pace.analytics_views
    pace.stats, pace.analytics_views = fake_stats, lambda *a, **k: {}
    try:
        man = _write_manifest(entries)
        good = pace.gate("dharma", man, token="x", scripts=scripts,
                         cues=("ลอง", "คืนนี้"))
        if good["verdict"] != "good" or good["last_shape"] != "cue":
            fail(f"a fast clip did not grade good: {good}")
        # Same last clip, but the channel's steady rate is now higher -> bad.
        def slow_stats(_tok, _ids):
            d = fake_stats(_tok, _ids)
            d["old1"] = {"views": 4800, "published_at": None}
            d["old2"] = {"views": 4000, "published_at": None}
            d["old3"] = {"views": 3000, "published_at": None}
            return d
        pace.stats = slow_stats
        bad = pace.gate("dharma", man, token="x", scripts=scripts,
                        cues=("ลอง", "คืนนี้"))
        if bad["verdict"] != "bad":
            fail(f"a clip below the channel median did not grade bad: {bad}")
        os.unlink(man)
    finally:
        pace.stats, pace.analytics_views = orig_stats, orig_av
    print("  gate: real counts grade good above the median and bad below it")


def test_wiring() -> None:
    src = open(os.path.join(HERE, "publish_shorts.py"), encoding="utf-8").read()
    if '"posted_at": posted_at' not in src:
        fail("publish_shorts no longer records posted_at; the gate has no clock")
    if "pace.gate(" not in src or "pace.order(" not in src:
        fail("publish_shorts does not use pace; the loop is not connected")
    fm = open(os.path.join(HERE, "foreman.py"), encoding="utf-8").read()
    if 'publish-shorts", {"per_run": "1"}' not in fm:
        fail("foreman still posts more than one Short per dispatch (a burst)")
    print("  wiring: publish records posted_at, uses pace; foreman posts one")


def main() -> int:
    test_gap()
    test_order()
    test_grade()
    test_gate_end_to_end()
    test_wiring()
    print("OK: one clip, 2-3 h apart, shape kept when good and changed when bad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
