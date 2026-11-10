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
        return {"old1": {"views": 480, "likes": 4, "comments": 1, "published_at": None},
                "old2": {"views": 400, "likes": 3, "comments": 0, "published_at": None},
                "old3": {"views": 300, "likes": 2, "comments": 1, "published_at": None},
                "last": {"views": 300, "likes": 5, "comments": 1, "published_at": None}}  # 100/h >> baseline

    orig_stats, orig_av = pace.stats, pace.analytics_views
    pace.stats, pace.analytics_views = fake_stats, lambda *a, **k: {}
    try:
        man = _write_manifest(entries)
        good = pace.gate("dharma", man, token="x", scripts=scripts,
                         cues=("ลอง", "คืนนี้"))
        if good["verdict"] != "good" or good["last_shape"] != "cue":
            fail(f"a fast clip did not grade good: {good}")
        # Same-day engagement proxy must be read in the same call (K, 2026-11-10).
        if good.get("likes") != 5 or good.get("engagement_per_1k") != 20.0:
            fail(f"gate did not report same-day likes/comments: {good}")
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


def test_stall() -> None:
    """The feed can stop showing a channel entirely -- that is not 'bad reception'.

    Measured 2026-11-10: kongkeat's last 37 clips sat at 0-2 views (feed off) while
    its first 14 held 40-242. A weak hook still gets *some* feed views; all-flat is
    reach removed, and posting more of the same deepens it (five-advisor panel,
    unanimous). detect_stall must tell the two apart.
    """
    def entries(n):
        return [(f"{i:02d}", {"video_id": f"v{i}", "posted_at": _iso(3 + i)})
                for i in range(1, n + 1)]

    flat = {f"v{i}": 0 for i in range(1, 6)}          # newest five, all zero
    r = pace.detect_stall(entries(6), flat)
    if not r["stalled"]:
        fail(f"five flat clips did not read as a feed stall: {r}")
    if r.get("last_hours") is None:
        fail("a stall did not report how long the feed has been off")

    mixed = {"v6": 120, "v5": 0, "v4": 0, "v3": 0, "v2": 0}
    r = pace.detect_stall(entries(6), mixed)
    if r["stalled"]:
        fail("a clip with real reach did not clear the stall; the channel is fine")

    r = pace.detect_stall(entries(3), {f"v{i}": 0 for i in range(1, 4)})
    if r["stalled"]:
        fail("stalled on too few clips; three flat clips is noise, not a verdict")

    # A spent quota (no view counts) must not be read as suppression.
    r = pace.detect_stall(entries(6), {})
    if r["stalled"]:
        fail("read a spent quota (no view data) as a feed stall")
    print("  stall: five flat clips stall, real reach clears, unknowns never stall")


def test_gate_stall() -> None:
    """gate() must pause a stalled channel, then allow ONE changed probe after a while."""
    def manifest(age_h):
        return _write_manifest({f"{i:02d}": {"video_id": f"v{i}", "posted_at": _iso(age_h + i)}
                                for i in range(1, 7)})

    flat = {f"v{i}": 0 for i in range(1, 7)}
    orig_stats, orig_av = pace.stats, pace.analytics_views
    pace.stats, pace.analytics_views = (lambda *a, **k: {k2: {"views": v, "published_at": None}
                                                         for k2, v in flat.items()}), (lambda *a, **k: {})
    try:
        recent = manifest(3.0)          # last clip 3 h ago, feed off
        r = pace.gate("kongkeat", recent, token="x")
        if r["allowed"]:
            fail(f"gate kept posting to a stalled channel: {r}")
        if r["verdict"] != "bad":
            fail("a stall did not read as a change-the-shape verdict")
        os.unlink(recent)
        old = manifest(30.0)            # last clip 30 h ago, past the cooldown
        r2 = pace.gate("kongkeat", old, token="x")
        if not r2["allowed"] or r2["verdict"] != "bad":
            fail(f"gate did not allow a single changed probe after the cooldown: {r2}")
        os.unlink(old)
    finally:
        pace.stats, pace.analytics_views = orig_stats, orig_av
    print("  gate: stalled channel pauses, then one changed probe is allowed")


def test_probe_voice() -> None:
    """A withheld channel's probe must SOUND different, not repeat the same voice.

    The five-advisor panel's recovery step is "change the voice/template", so the
    probe has to be a real alternative: make_short exposes VOICE_ALT and a --probe
    flag, and the rail must pass --probe (and rebuild, not reuse) on a stalled run.
    """
    import make_short
    if make_short.VOICE_ALT == make_short.VOICE:
        fail("VOICE_ALT is the same as VOICE; the probe would not change anything")
    ms = open(os.path.join(HERE, "make_short.py"), encoding="utf-8").read()
    if '"--probe"' not in ms or "args.voice = VOICE_ALT" not in ms:
        fail("make_short does not turn --probe into the alternate voice")
    ps = open(os.path.join(HERE, "publish_shorts.py"), encoding="utf-8").read()
    if 'cmd += ["--probe"]' not in ps:
        fail("publish_shorts does not pass --probe on a stalled run")
    if "if stalled or not os.path.exists(out):" not in ps:
        fail("a stalled run would reuse the cached build instead of rebuilding the probe")
    print("  probe: a stalled channel comes back with the alternate voice, rebuilt")


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
    test_stall()
    test_gate_stall()
    test_probe_voice()
    test_wiring()
    print("OK: one clip, 2-3 h apart, shape kept when good and changed when bad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
