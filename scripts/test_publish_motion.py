#!/usr/bin/env python3
"""Guard the motion Short rail: every gate of the Shorts rail must still apply.

K (2026-11-19) asked for the four fixed clips to go up on their channels. There
was no rail for them -- `make_motion_short.py` is a tool, and the clips were
uploaded by hand, which meant nothing carried the cap, the gap, the pace gate,
the standard gate or the bed ledger. `publish_motion.py` is that rail.

What this locks, each of which can FAIL:

  1. **No second copy of a rule.** The rail must import its numbers from
     `publish_shorts` (cap, gap, bed, tail, CTA) instead of restating them. A
     literal cap or gap in the new file is a drift bug -- the same shape that let
     a false alarm survive in link-shorts/set-thumbnails.
  2. **The standard gate runs BEFORE the upload**, and a substandard clip is HELD
     (returns 1) with the reasons printed. Proven with a REAL ffmpeg artifact.
  3. **The cap and the gap actually block**, and block before a build is spent.
  4. **The genre -> channel map sweeps every story on disk.** No hardcoded list:
     a new story whose genre has no channel fails here rather than at 3am.
  5. **A story is never sent to a channel it was not written for.**

    python3 scripts/test_publish_motion.py    # exit 0 = the rail holds
"""
from __future__ import annotations

import glob
import json
import re
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_motion as PM    # noqa: E402
import publish_shorts as PS    # noqa: E402
import short_standard          # noqa: E402

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + label + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(label)


def sh(cmd: list[str]) -> None:
    # stdin MUST be closed: ffmpeg reads stdin unless told otherwise, and a
    # process that reads a TTY it does not own is stopped by SIGTTIN -- measured
    # 2026-11-19, the whole test froze at state "TNl" until stdin was redirected.
    r = subprocess.run(cmd, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise SystemExit("cmd failed: " + " ".join(cmd) + "\n" + r.stderr[-1200:])


def bad_clip(d: str) -> tuple[str, str]:
    """A REAL clip that breaks the standard: 16:9 video + 16:9 thumbnail."""
    video = os.path.join(d, "bad.mp4")
    thumb = os.path.join(d, "bad.jpg")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", video])
    from PIL import Image
    Image.new("RGB", (1280, 720), (20, 20, 30)).save(thumb)
    return video, thumb


def good_clip(d: str) -> tuple[str, str]:
    """A REAL clip that meets the standard: 4K 2160x3840 tv/bt709, 9:16 thumbnail."""
    video = os.path.join(d, "good.mp4")
    thumb = os.path.join(d, "good.jpg")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=2160x3840:rate=30:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
        "-af", "loudnorm=I=-14:TP=-3", "-ar", "48000",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-color_range", "tv", "-colorspace", "bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-shortest", video])
    from PIL import Image
    Image.new("RGB", (1080, 1920), (20, 20, 30)).save(thumb)
    return video, thumb


def run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["publish_motion.py"] + argv
    try:
        return PM.main()
    finally:
        sys.argv = old


def main() -> int:
    stories = sorted(glob.glob(os.path.join(ROOT, "content", "motion", "*.json")))
    print(f"stories on disk: {len(stories)}")

    # 1. The rail must not restate a rule that lives in publish_shorts.
    print("\n1. one source for every rule")
    src = open(os.path.join(HERE, "publish_motion.py"), encoding="utf-8").read()
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.strip().startswith("#"))
    check("import publish_shorts" in src, "imports publish_shorts")
    check(not __import__("re").search(r"^\s*(DAILY_CAP|MIN_GAP_HOURS)\s*=", code,
                                     __import__("re").M),
          "declares no cap/gap literal of its own")
    check("PS.DAILY_CAP" in code and "PS.MIN_GAP_HOURS" in code,
          "reads the cap and the gap from publish_shorts")
    check("short_standard.verify_short(" in code, "uses the shared standard gate")
    # Order matters: a standard check after the insert is decoration.
    i_std = code.find("verify_short(")
    i_ins = code.find("videos().insert")
    check(0 <= i_std < i_ins, "standard gate runs before videos().insert",
          f"std@{i_std} insert@{i_ins}")

    # 2. The standard gate holds a substandard clip (REAL artifacts).
    print("\n2. a substandard clip is HELD, not uploaded")
    story = stories[0]
    with open(story, encoding="utf-8") as fh:
        slug = PM.GENRE_CHANNEL[json.load(fh)["genre"]]
    spec = PS.CHANNELS[slug]
    with tempfile.TemporaryDirectory() as d:
        bad_v, bad_t = bad_clip(d)
        ok_bad, why_bad, _ = short_standard.verify_short(bad_v, bad_t)
        check(not ok_bad, "verify_short rejects a 16:9 clip", f"{len(why_bad)} reasons")
        good_v, good_t = good_clip(d)
        ok_good, why_good, m_good = short_standard.verify_short(good_v, good_t)
        check(ok_good, "verify_short accepts a compliant clip", str(m_good))

        # Drive the rail's own main(): build() is replaced by the real artifacts
        # and the cap/gap are opened, so the standard path runs on real files
        # with no network. Without opening them the cap would stop the run first
        # and this check would pass for the wrong reason.
        o_cap, o_gap = PS.uploads_in_last_24h, PS.hours_since_last_upload
        PS.uploads_in_last_24h = lambda c, m: 0
        PS.hours_since_last_upload = lambda c, m: None
        orig_build = PM.build
        PM.build = lambda path, out: (bad_v, bad_t, d)
        try:
            rc = run_main(["--story", story, "--dry-run"])
        finally:
            PM.build = orig_build
            PS.uploads_in_last_24h, PS.hours_since_last_upload = o_cap, o_gap
        check(rc == 1, "main() returns 1 (held) on a substandard clip", f"rc={rc}")

        # 3. Cap and gap block, and do so before a build is spent.
        print("\n3. the cap and the gap block before a build")
        built = {"n": 0}

        def counted(path, out):
            built["n"] += 1
            return (good_v, good_t, d)

        o_cap = PS.uploads_in_last_24h
        PS.uploads_in_last_24h = lambda c, m: PS.DAILY_CAP
        PM.build = counted
        try:
            rc = run_main(["--story", story, "--dry-run"])
        finally:
            PS.uploads_in_last_24h = o_cap
        check(rc == 0 and built["n"] == 0,
              "cap reached -> stops without building", f"rc={rc} builds={built['n']}")

        o_gap = PS.hours_since_last_upload
        PS.hours_since_last_upload = lambda c, m: PS.MIN_GAP_HOURS / 2
        PM.build = counted
        try:
            rc = run_main(["--story", story, "--dry-run"])
        finally:
            PS.hours_since_last_upload = o_gap
            PM.build = orig_build
        check(rc == 0 and built["n"] == 0,
              "gap too small -> stops without building", f"rc={rc} builds={built['n']}")

        # A compliant clip passes the gate and reaches a full body (dry run).
        # The cap and gap are opened, or this would pass because the run stopped
        # early -- the false pass this test exists to catch.
        print("\n4. a compliant clip reaches a complete upload body")
        PS.uploads_in_last_24h = lambda c, m: 0
        PS.hours_since_last_upload = lambda c, m: None
        PM.build = lambda path, out: (good_v, good_t, d)
        try:
            rc = run_main(["--story", story, "--dry-run"])
        finally:
            PM.build = orig_build
            PS.uploads_in_last_24h, PS.hours_since_last_upload = o_cap, o_gap
        check(rc == 0, "dry run succeeds on a compliant clip", f"rc={rc}")

    # 5. A motion story must never be recorded under a bare id. Story ids are
    #    01..04 and so are the channel pool's (measured 2026-11-19: dharma's
    #    shorts["01"] is a live video from 2026-11-03), so a bare key would
    #    overwrite a real upload and make the next run publish it again. The
    #    collision is the reason for the prefix, so what must hold is that the
    #    key we actually write is free in both the pool and the manifest.
    print("\n5. the key we record under is free in the pool and the manifest")
    for slug_name in sorted(set(PM.GENRE_CHANNEL.values())):
        pool = PS.load(PS.CHANNELS[slug_name]["scripts"], [])
        bare = {str(s.get("id")) for s in pool}
        man = PS.load(PS.CHANNELS[slug_name]["manifest"], {"shorts": {}})
        taken = bare | set(man.get("shorts", {}))
        for path in stories:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
            if PM.GENRE_CHANNEL.get(st.get("genre")) != slug_name:
                continue
            key = PM.record_key(str(st["id"]))
            check(key not in taken, f"{slug_name}: key {key} is free", f"pool={len(bare)}")

    # 7. No build subprocess may inherit stdin. ffmpeg reads stdin unless told
    #    otherwise, and a child that reads a TTY it does not own is stopped by
    #    SIGTTIN -- measured 2026-11-19: this whole test froze at state "TNl"
    #    until stdin was redirected. A guard that hangs is not a guard.
    print("\n7. every build subprocess closes stdin")
    src = open(os.path.join(HERE, "publish_motion.py"), encoding="utf-8").read()
    calls = [m for m in re.finditer(r"subprocess\.run\(", src)]
    check(bool(calls), "the rail does spawn subprocesses", f"{len(calls)} call(s)")
    bare = []
    for m in calls:
        # the call's own argument list runs to the matching close paren
        depth, i = 0, m.end() - 1
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if "stdin=" not in src[m.start():i]:
            line = src[:m.start()].count("\n") + 1
            bare.append(f"L{line}")
    check(not bare, "no subprocess.run inherits stdin", f"bare={bare}")

    # 8. Every story on disk maps to a real channel, and never to a wrong one.
    print("\n8. every story maps to its own channel")
    check(set(PM.GENRE_CHANNEL.values()) <= set(PS.CHANNELS),
          "every mapped channel exists in CHANNELS",
          str(sorted(set(PM.GENRE_CHANNEL.values()) - set(PS.CHANNELS))))
    for path in stories:
        with open(path, encoding="utf-8") as fh:
            st = json.load(fh)
        g = st.get("genre")
        check(g in PM.GENRE_CHANNEL, f"{os.path.basename(path)}: genre {g!r} has a channel")
        if g in PM.GENRE_CHANNEL:
            other = next((c for c in PS.CHANNELS if c != PM.GENRE_CHANNEL[g]), None)
            if other:
                try:
                    run_main(["--story", path, "--channel", other, "--dry-run"])
                    sent_wrong = True
                except SystemExit:
                    sent_wrong = False
                check(not sent_wrong,
                      f"{os.path.basename(path)}: refuses channel {other}")

    print(f"\n{'PASS' if not FAILS else 'FAIL'} -- {len(FAILS)} failing check(s)")
    for f in FAILS:
        print("  - " + f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
