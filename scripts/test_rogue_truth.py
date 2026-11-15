#!/usr/bin/env python3
"""Our docs must name the REAL cause of the "rogue" stream -- and must not send K
on a wild goose chase.

Measured 2026-11-15: the rogue uploader is our own predecessor rail
`kongkeat938/ax-workspace` workflow `auto-shorts` (same channels, same
`YT_CH*_REFRESH_TOKEN` secrets). It was fixed with no human login. An earlier
version of `docs/K-PHONE-ACTION.md` told K to rotate the GCP client secret -- which
would have killed OUR rails for no reason.

This guard can FAIL: strip the real cause from any doc (or put the "RESET SECRET"
instruction back) and it exits 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        fail(f"{rel} is missing")
    return p.read_text(encoding="utf-8")


def main() -> int:
    for rel in ("docs/PCSEV-2026-11-15-rogue.md", "docs/K-PHONE-ACTION.md",
                ".openhands/memory/MEMORY.md"):
        text = read(rel)
        for needed in ("ax-workspace", "auto-shorts"):
            if needed not in text:
                fail(f"{rel} does not name the real cause ({needed!r}); a doc that "
                     f"blames an external attacker is the bug K rejected")

    # The old K-PHONE-ACTION told K to RESET SECRET in GCP. That breaks our rails.
    kphone = read("docs/K-PHONE-ACTION.md")
    if "RESET SECRET" in kphone:
        fail("docs/K-PHONE-ACTION.md still tells K to reset the GCP client secret, "
             "which would kill our own rails -- the rogue stream needs no human login")
    if "ไม่ต้องทำอะไรบนมือถือ" not in kphone and "ไม่ต้องแตะมือถือ" not in kphone:
        fail("docs/K-PHONE-ACTION.md no longer states that K has nothing to do on "
             "the phone")

    print("OK: every doc names ax-workspace auto-shorts as the cause, and K is told "
          "there is nothing to do on the phone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
