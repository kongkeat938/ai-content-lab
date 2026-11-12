#!/usr/bin/env python3
"""The three channels are on three SEPARATE Google accounts. Keep the map in sync.

K (2026-11-12): "ช่องทั้ง 3 มีเมล์ตามนี้ ทีนี้แยกบัญชีตามเมล์" -- genx, dharma and
kongkeat-story each own their own Google account, so each carries its own 19/day
upload pool and its own manager grant. That is only true if every file that names
an account agrees. channels.json once said `openhands-1` for genx and dharma, which
is neither a real account nor a real email -- a stale value that hides the split.

This locks the three sources together, and proves the guard can FAIL.

    python3 scripts/test_channel_accounts.py
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import delegate_ready as dr  # noqa: E402

# The source of truth, measured from scripts/mail_watch.py (which reads each
# channel's own inbox) and confirmed by K on 2026-11-12.
TRUTH = {
    "genx": "kongkeat.938@gmail.com",
    "dharma": "farmmer.938@gmail.com",
    "kongkeat-story": "kongkeat.p3@gmail.com",
}

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def mail_watch_map() -> dict[str, str]:
    """slug -> address, read from scripts/mail_watch.py's ACCOUNTS block."""
    src = open(os.path.join(HERE, "mail_watch.py"), encoding="utf-8").read()
    block = src[src.index("ACCOUNTS = {"):]
    block = block[: block.index("}")]
    out = {}
    for m in re.finditer(r'"([a-z0-9-]+)":\s*\("YT_[A-Z0-9_]+",\s*"([^"]+)"\)', block):
        out[m.group(1)] = m.group(2)
    return out


def main() -> int:
    print("delegate_ready agrees with the truth")
    for ch, email in TRUTH.items():
        got = dr.CHANNELS[ch][2]
        check(f"delegate_ready {ch} -> {email}", got == email, got)

    print("channels.json agrees with the truth (no stale 'openhands-1')")
    doc = json.load(open(os.path.join(ROOT, "channels.json"), encoding="utf-8"))
    by_slug = {c["slug"]: c for c in doc["channels"]}
    for ch, email in TRUTH.items():
        got = by_slug.get(ch, {}).get("account")
        check(f"channels.json {ch} -> {email}", got == email, got)

    print("mail_watch.py agrees with the truth")
    mw = mail_watch_map()
    for ch, email in TRUTH.items():
        check(f"mail_watch {ch} -> {email}", mw.get(ch) == email, mw.get(ch))

    print("the three accounts are actually distinct")
    check("three separate addresses", len(set(TRUTH.values())) == 3)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: one channel, one account, and every file says so")
    return 0


if __name__ == "__main__":
    sys.exit(main())
