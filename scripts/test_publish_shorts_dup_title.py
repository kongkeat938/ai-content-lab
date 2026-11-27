#!/usr/bin/env python3
"""A title that is already live must be refused before the upload starts.

Measured 2026-11-27: 13 Shorts repeated a title the channel already carried (one
title four times on genx), against K's rule that nothing repeats. The manifest
cannot see this -- it only knows what the rails recorded -- so the rail now reads
the channel's live titles and holds a repeat.

    python3 scripts/test_publish_shorts_dup_title.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


class FakeYt:
    """Two pages of uploads, the way the real playlist answers."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def channels(self):
        return self

    def playlistItems(self):  # noqa: N802 - mirror the client's name
        return self

    def list(self, **kw):
        self.calls.append(kw)
        if kw.get("part") == "contentDetails":
            return self
        return self

    def execute(self):
        if "playlistId" not in self.calls[-1]:
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        page = self.calls[-1].get("pageToken")
        idx = int(page or 0)
        body = self.pages[idx]
        out = {"items": [{"snippet": {"title": t}} for t in body]}
        if idx + 1 < len(self.pages):
            out["nextPageToken"] = str(idx + 1)
        return out


def main() -> int:
    # 1. the normalisation has to make the live form and the rail form comparable
    live_title = "คุณมีสิทธิ์เดินช้าลงในวันที่โลกหมุนเร็วจนเหนื่อย"
    rail_title = "คุณมีสิทธิ์เดินช้าลงในวันที่โลกหมุนเร็วจนเหนื่อย #Shorts"
    check("a hashtag does not hide a repeat",
          ps.norm_title(rail_title) == ps.norm_title(live_title),
          f"{ps.norm_title(rail_title)!r} != {ps.norm_title(live_title)!r}")
    check("case and spacing do not hide a repeat",
          ps.norm_title("  Hello  World #Shorts ") == ps.norm_title("hello world"))
    check("the rail form is a repeat", ps.title_is_repeat(rail_title, {ps.norm_title(live_title)}))
    check("a fresh title is not a repeat",
          not ps.title_is_repeat("เรื่องใหม่เอี่ยม #Shorts", {ps.norm_title(live_title)}))

    # 2. the live read must page, or the oldest duplicates stay invisible
    yt = FakeYt([["A title #Shorts", "B title"], ["C title #Shorts"]])
    got = ps.live_titles(yt, "UC_TEST")
    check("both pages are read", {"a title", "b title", "c title"} == got, str(sorted(got)))
    check("the guard can fail: an empty channel matches nothing",
          not ps.title_is_repeat("A title #Shorts", ps.live_titles(FakeYt([[]]), "UC_TEST")))

    # 3. the gate has to be wired into the publish path, not just available
    src = open(os.path.join(HERE, "publish_shorts.py"), encoding="utf-8").read()
    check("the loop consults the gate", "if title_is_repeat(title, live):" in src)
    check("a repeat is held, not uploaded", "HELD -- this title is already live" in src)
    check("an unreadable channel is BLIND (exit 2), never a silent pass",
          "refusing to publish without the duplicate check" in src and "        return 2" in src)
    check("the upload body reuses the checked title", '"title": title,' in src)

    bad = [n for n, ok, _ in CHECKS if not ok]
    print()
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed" if not bad
          else f"FAIL: {len(bad)} check(s): {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
