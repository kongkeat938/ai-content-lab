#!/usr/bin/env python3
"""The delegation check must FAIL honestly: a copy of the primary is NOT delegation.

K chose B (2026-11-12): a second account as manager, so the team can act without
him. A "delegated" secret that is really the primary copied across is not a second
account -- it is the same grant wearing a new name, and it proves nothing.

A delegated token is also bound to the OAuth client that minted it, so a token from
a second client must be exchanged with *that* client. A wrong client answers
`unauthorized_client`, which is not a working credential -- it must never read as
READY. This locks both distinctions, and proves the guard can FAIL.

    python3 scripts/test_delegate_ready.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import delegate_ready as dr  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("no delegated secret is a real gap")
    check("missing alt -> NOT-DELEGATED", dr.status("P", None)[0] == "NOT-DELEGATED")

    print("a copy of the primary is NOT a delegation (the guard can fail)")
    v, _ = dr.status("SAME", "SAME")
    check("alt == primary -> NOT-DELEGATED", v == "NOT-DELEGATED", v)

    print("a broken delegated token is NOT-DELEGATED, never a false READY")
    # No client creds -> cannot exchange -> must not claim READY.
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET"):
        os.environ.pop(k, None)
    v, _ = dr.status("primary", "a-different-token")
    check("unexchangeable alt -> NOT-DELEGATED", v == "NOT-DELEGATED", v)

    print("a token is checked with its OWN client, not only the primary (the guard can fail)")
    # Simulate a real exchange: the token works only under client "B". A checker that
    # only ever tried the primary client ("A") would report NOT-DELEGATED -- the bug
    # this fix removes -- so READY must require trying the matching client.
    real = dr.exchanges
    client_a, client_b = ("id-a", "sec-a"), ("id-b", "sec-b")
    dr.exchanges = lambda tok, cl=None: cl == client_b
    try:
        v, _ = dr.status("primary", "alt-token", clients=[client_a, client_b])
        check("matching client -> READY", v == "READY", v)
        v, _ = dr.status("primary", "alt-token", clients=[client_a])
        check("primary client only -> NOT-DELEGATED", v == "NOT-DELEGATED", v)
    finally:
        dr.exchanges = real

    print("the three active channels are mapped")
    check("genx/dharma/kongkeat-story present",
          set(dr.CHANNELS) == {"genx", "dharma", "kongkeat-story"})

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: delegation readiness cannot be faked by copying the primary")
    return 0


if __name__ == "__main__":
    sys.exit(main())
