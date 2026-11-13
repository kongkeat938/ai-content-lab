#!/usr/bin/env python3
"""ak must remember it has its own profile and mailbox.

K (2026-11-13): "Ak ลืมไปหรือยังว่า ak มีโปรไฟล์และเมลของตัวเอง". The old note lived only
in the `ax-workspace` repo and a PC1 vault that died, so a fresh session never saw it and ak
kept asking K for an email. This guard makes the knowledge un-forgettable: the identity doc
must exist, name the mailbox provider, and the helper must expose its subcommands.

It can FAIL: delete `docs/AK-IDENTITY.md`, or strip `ak_mail.py` of a subcommand, and it
exits 1. A guard that only checks the happy path proves nothing.

    python3 scripts/test_ak_identity.py     # exit 0 = ak's identity is recorded
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOC = os.path.join(ROOT, "docs", "AK-IDENTITY.md")
HELPER = os.path.join(HERE, "ak_mail.py")
MAP = os.path.join(ROOT, "docs", "PROJECT-MAP.md")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    if not os.path.exists(DOC):
        fail("docs/AK-IDENTITY.md is missing -- ak's own identity is not recorded, so it "
             "will be forgotten again on the next recycle")
    doc = open(DOC, encoding="utf-8").read()
    for needed in ("mail.tm", "never signs up as K", "KV vault"):
        if needed not in doc:
            fail(f"docs/AK-IDENTITY.md does not mention {needed!r}")

    if not os.path.exists(HELPER):
        fail("scripts/ak_mail.py is missing -- ak cannot read its own mailbox headlessly")
    helper = open(HELPER, encoding="utf-8").read()
    for sub in ('"new"', '"show"', '"inbox"', '"read"'):
        if sub not in helper:
            fail(f"scripts/ak_mail.py is missing the {sub} subcommand")

    if not os.path.exists(MAP) or "AK-IDENTITY" not in open(MAP, encoding="utf-8").read():
        fail("docs/PROJECT-MAP.md does not point at AK-IDENTITY.md")

    print("OK: ak's identity doc, mailbox helper and map pointer are all present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
