#!/usr/bin/env python3
"""The Shorts description must lead with the long-form link.

A Shorts viewer who taps "more" sees one line before scrolling, so a link buried
under the transcript is a link nobody taps. This guard sweeps every channel spec
instead of a fixed set, so a new channel that ships its link in the tail is
caught here rather than by a missing click.

    python3 scripts/test_shorts_description.py
"""
from __future__ import annotations

import sys

import publish_shorts as ps

S = {"hook": "คืนนี้ลองวางมือบนท้องแล้วหายใจช้าๆ",
     "lines": ["ปิดไฟแล้วนอนหงาย", "วางมือบนท้อง"],
     "cta": "กดติดตามช่องเพื่อฟังธรรมะเต็มบทก่อนนอน"}

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main() -> int:
    checked = 0
    for name, spec in ps.CHANNELS.items():
        urls = [w for w in spec.get("tail", "").split() if w.startswith("http")]
        if not urls:
            continue
        checked += 1
        desc = ps.build_description(S, spec)
        first = desc.splitlines()[0]
        check(any(u in first for u in urls),
              f"{name}: long-form link is the first line")
        check(S["hook"] in desc and S["cta"] in desc,
              f"{name}: hook and CTA survive")
        check(all(u in desc for u in urls), f"{name}: every link kept")
        last = [ln for ln in desc.splitlines() if ln.strip()][-1]
        if "#" in spec["tail"]:
            check(last.startswith("#"), f"{name}: hashtags stay last")

    # A spec with no link must not invent one, and must not lose the hook.
    bare = ps.build_description(S, {"tail": "\n\n#แท็ก"})
    check(bare.startswith(S["hook"]), "no-link spec still leads with the hook")
    check("http" not in bare, "no-link spec invents no URL")

    # The seam must be able to FAIL: a tail whose link is not at the top is caught.
    broken = {"tail": "\n\nอ่านต่อ\nhttps://youtu.be/x\n\n#แท็ก"}
    first_broken = ps.build_description(S, broken).splitlines()[0]
    check("https://youtu.be/x" not in first_broken or "อ่านต่อ" in first_broken,
          "detector would catch a link below a stray line")

    check(checked >= 3, f"swept every channel spec ({checked})")
    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
