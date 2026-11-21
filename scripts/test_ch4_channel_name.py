#!/usr/bin/env python3
"""Guard: no ch4 rail may write the retired channel name back.

The ch4 channel is named **PCSEV** (K set it in Studio 2026-11-17; the main title
is not API-settable, so the repo follows the live name). The genre is still
"เกร็ดความรู้รอบตัว" (knowledge / why-question videos) -- that word is legitimate in
keywords, SEO text, themes and the description, so this guard must NOT ban it
everywhere. It pins only the places where the string is the CHANNEL NAME, i.e. a
label a viewer sees as the channel, or a phrase a rail writes into a live video
description / published title.

Two checks:
  1. The channel-name LABELS and the channel-name PHRASES a live rail writes are
     "PCSEV", not the retired "เกร็ดความรู้รอบตัว".
  2. `scrub_channel_name.py` scrubs the pivot channel-name phrasings but never the
     bare genre word (proved by running its REPLACEMENTS over a sample).

This guard can FAIL: set a label back to the old name, or drop the phrase scrub,
and it exits 1.

    python3 scripts/test_ch4_channel_name.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

OLD = "เกร็ดความรู้รอบตัว"
NEW = "PCSEV"

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def read(rel: str) -> str:
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def label_is_pcsev() -> None:
    """Every channel-name LABEL for ch4 says PCSEV."""
    import analyze_reach
    import progress
    import report_reach
    check("progress.LABEL[kongkeat] = PCSEV", progress.LABEL["kongkeat"] == NEW,
          progress.LABEL["kongkeat"])
    check("analyze_reach label = PCSEV",
          analyze_reach.CHANNELS["kongkeat"][2] == NEW, analyze_reach.CHANNELS["kongkeat"][2])
    check("report_reach label = PCSEV",
          report_reach.CHANNELS["kongkeat"][2] == NEW, report_reach.CHANNELS["kongkeat"][2])


def live_writers_are_pcsev() -> None:
    """The phrases a rail writes into a LIVE description / title say PCSEV."""
    import channel_overhaul
    import promote_channels
    import scrub_channel_name as scn

    titles = [p["title"] for p in channel_overhaul.PLAN["ch4"]["playlists"]]
    check("channel_overhaul ch4 playlist titles start with PCSEV",
          all(t.startswith(NEW) for t in titles), str(titles))
    check("channel_overhaul CHANNELS[ch4] name = PCSEV",
          channel_overhaul.CHANNELS["ch4"]["name"] == NEW,
          channel_overhaul.CHANNELS["ch4"]["name"])
    check("promote_channels SIBLING[dharma] names PCSEV",
          promote_channels.SIBLING["dharma"][0] == NEW, promote_channels.SIBLING["dharma"][0])
    check("scrub NEW_NAME = PCSEV", scn.NEW_NAME == NEW, scn.NEW_NAME)
    check("scrub SIBLING_NEW starts with PCSEV", scn.SIBLING_NEW.startswith(NEW),
          scn.SIBLING_NEW)

    # add_release_to_manifest builds a live description: it must name PCSEV.
    ar = read("scripts/add_release_to_manifest.py")
    check("add_release_to_manifest sibling line names PCSEV",
          f"ช่องพี่น้อง —\\n{NEW} " in ar)
    check("add_release_to_manifest follow line names PCSEV",
          f"ฝากกดติดตามช่อง {NEW} " in ar)

    # The published long-form TITLE prefix must be the channel name.
    wf = read(".github/workflows/ch4-longform.yml")
    check("ch4-longform published TITLE prefix = PCSEV", f'TITLE="{NEW} — ' in wf)

    # The SEO theme names the channel ("ช่อง <name> …"), so it must say PCSEV.
    seo = read("scripts/optimize_seo.py")
    check("optimize_seo ch4 theme names the channel PCSEV", f"ช่อง {NEW} " in seo)


def scrub_is_surgical() -> None:
    """The scrub rewrites the channel-name phrasing but keeps the genre word."""
    import scrub_channel_name as scn

    sample = ("รวมเกร็ดความรู้รอบตัวน่าทึ่ง 30 นาที\n"
              "ฝากกดติดตามช่อง เกร็ดความรู้รอบตัว เพื่อรับเกร็ดน่ารู้ใหม่ทุกสัปดาห์")
    out = sample
    for old, new in scn.REPLACEMENTS:
        out = out.replace(old, new)
    check("scrub keeps the genre word 'รวมเกร็ดความรู้รอบตัวน่าทึ่ง'",
          "รวมเกร็ดความรู้รอบตัวน่าทึ่ง" in out, out)
    check("scrub rewrites the follow phrase to PCSEV",
          f"ฝากกดติดตามช่อง {NEW} " in out and f"ฝากกดติดตามช่อง {OLD} " not in out, out)
    # The bare word must NOT be in the token set, or the genre text would be hit.
    check("bare genre word is not an OLD_TOKEN", OLD not in scn.OLD_TOKENS, str(scn.OLD_TOKENS))


def rename_survives_quota() -> None:
    """A live shelf may still carry an old title until quota lets the rename land.

    Both the rename (channel_overhaul) and the door (short_doors) must accept the
    old titles, or the rename splits the playlist / the door loses its link.
    """
    import channel_overhaul as co
    import short_doors as sd

    plans = co.PLAN["ch4"]["playlists"]
    for spec in plans:
        rf = spec.get("rename_from")
        rf = rf if isinstance(rf, list) else [rf]
        check(f"channel_overhaul '{spec['title']}' rename_from covers the live titles",
              "เรื่องเล่าอบอุ่นใจ — Shorts" in rf or "เรื่องเล่าอบอุ่นใจ — ตอน" in rf, str(rf))

    routes = sd.CHANNELS["ch4"]["routes"]
    names = routes[0][0]
    check("short_doors ch4 route lists PCSEV + the old titles",
          isinstance(names, list) and names[0].startswith(NEW)
          and "เรื่องเล่าอบอุ่นใจ — Shorts" in names, str(names))
    # route() must return a title that exists, so the link stays real pre-rename.
    check("short_doors route() prefers an existing old title",
          sd.route("x", routes, {"เรื่องเล่าอบอุ่นใจ — Shorts": "PL1"})
          == "เรื่องเล่าอบอุ่นใจ — Shorts")
    check("short_doors route() uses the new title once it exists",
          sd.route("x", routes, {f"{NEW} — เกร็ดสั้น": "PL2"}) == f"{NEW} — เกร็ดสั้น")


RETIRED_GENRE = ("เรื่องเล่าอบอุ่นใจ", "รวมเรื่องครอบครัว")


def queue_problems(manifest: dict) -> list[str]:
    """The real failure mode: a retired-genre video queued for a knowledge channel."""
    out = []
    for v in manifest.get("videos", []):
        if v.get("state") == "published":
            continue
        title = str(v.get("title", ""))
        if any(g in title for g in RETIRED_GENRE):
            out.append(f"pending {v.get('key')} carries the retired genre: {title[:40]}")
    return out


def queue_is_knowledge() -> None:
    import json

    man = json.load(open(os.path.join(ROOT, "content", "ch4_publish.json"), encoding="utf-8"))
    bad = queue_problems(man)
    check("no PENDING ch4 entry carries the retired family genre", not bad, "; ".join(bad))
    fake = {"videos": [{"key": "x", "state": "queued",
                        "title": "เรื่องเล่าอบอุ่นใจ รวมเรื่องครอบครัว 3"}]}
    check("the queue check can FAIL", len(queue_problems(fake)) == 1, str(queue_problems(fake)))


def main() -> int:
    print("ch4 channel-name labels are PCSEV")
    label_is_pcsev()
    print("live-description writers name PCSEV")
    live_writers_are_pcsev()
    print("the scrub is surgical (genre word survives)")
    scrub_is_surgical()
    print("the rename survives the quota wait")
    rename_survives_quota()
    print("the long-form queue stays knowledge-only")
    queue_is_knowledge()
    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: ch4's channel name is PCSEV everywhere a rail would write it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
