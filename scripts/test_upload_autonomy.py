#!/usr/bin/env python3
"""ak publishes on its own — and nothing may quietly put an approval gate back.

K (2026-11-21): "ตอนนี้ระบบสร้างคลิปได้มาตรฐานแล้ว ยกเลิกกฏรอ K อนุมัติอัพออกเลย
อัพได้ตลอดเวลาเลย แล้วแต่ ak บริหาร". The gates still bind; the human approval step does not.

This guard sweeps the three documents that state the rule and the four scripts that
actually publish, and it proves itself by feeding a doc set that still demands K's
approval through the same checks -- a check that cannot fail proves nothing.

    python3 scripts/test_upload_autonomy.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DOCS = ["AGENTS.md", ".openhands/memory/MEMORY.md", "docs/PROJECT-MAP.md"]
PUBLISHERS = ["publish_shorts.py", "add_release_to_manifest.py", "publish_motion.py",
              "shorts_from_long.py"]

# An affirmative claim that a publish waits for K. The AGENTS.md line that *retires* the
# rule says "the old ... rule is gone", so only bolded / standalone claims count.
FORBIDDEN = [
    r"\*\*K alone approves",
    r"Only K approves a publish",
    r"upload only when K orders",
    r"K\s*คนเดียวอนุมัติ",
    r"ak does not upload",
    r"(?<!ยกเลิกกฏ)รอ\s*K\s*อนุมัติ",   # the quote of the *removal* is allowed
]
AUTONOMY = ["ak publishes on its own", "อัพได้ตลอดเวลา"]


def doc_problems(docs: dict[str, str]) -> list[str]:
    out = []
    for name, text in docs.items():
        for pat in FORBIDDEN:
            if re.search(pat, text):
                out.append(f"{name}: still carries the retired approval rule ({pat})")
    joined = "\n".join(docs.values())
    if not any(p in joined for p in AUTONOMY):
        out.append("no document states the autonomy rule -- it was dropped, not retired")
    return out


def publisher_problems(scripts: dict[str, str]) -> list[str]:
    out = []
    for name, text in scripts.items():
        for needle in ("docs/reviews", "review_ledger", "await_approval", "approval_required"):
            if needle in text:
                out.append(f"{name}: publish path still consults an approval gate ({needle})")
    return out


def cap_problems() -> list[str]:
    """Autonomy is not a flood: the Short uploader must hold on cap and gap."""
    from datetime import datetime, timedelta, timezone

    sys.path.insert(0, HERE)
    import shorts_from_long as S

    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    cid = "UCI6EfsgM1HNjrYarvigxyrQ"
    out = []
    if S.cap_block(cid, {"channels": {cid: [(now - timedelta(minutes=30)).isoformat()]}}, now) is None:
        out.append("the uploader allows a second upload 30 min after the last one")
    stamps = [(now - timedelta(hours=h)).isoformat() for h in (1, 5, 9)]
    if S.cap_block(cid, {"channels": {cid: stamps}}, now) is None:
        out.append("the uploader ignores the daily cap")
    if S.cap_block(cid, {"channels": {cid: [(now - timedelta(hours=3)).isoformat()]}}, now):
        out.append("the uploader refuses a legitimate upload 3 h after the last one")
    return out


def main() -> int:
    docs = {}
    for rel in DOCS:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            docs[rel] = fh.read()
    scripts = {}
    for name in PUBLISHERS:
        with open(os.path.join(ROOT, "scripts", name), encoding="utf-8") as fh:
            scripts[name] = fh.read()

    bad = doc_problems(docs) + publisher_problems(scripts) + cap_problems()
    for b in bad:
        print(f"FAIL: {b}")
    if bad:
        return 1

    # The guard must be able to FAIL.
    stale = {"AGENTS.md": "**Only K approves a publish.** The ledger decides.",
             "docs/PROJECT-MAP.md": "upload only when K orders"}
    caught = doc_problems(stale)
    if len(caught) < 2:
        print(f"FAIL: the guard let a stale approval rule through ({caught})")
        return 1
    print(f"OK: ak publishes on its own in {len(docs)} doc(s) and {len(scripts)} publish "
          f"path(s); the guard rejects a stale rule in {len(caught)} ways")
    return 0


if __name__ == "__main__":
    sys.exit(main())
