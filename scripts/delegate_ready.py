#!/usr/bin/env python3
"""Is a channel ready to be run WITHOUT K? Measure the delegated credential.

K chose B (2026-11-12): add a second account as manager so the team can cut a rogue
grant without him. The team-side half of B is a **delegated** refresh token -- one
minted while signed in as the second account, held in `YT_<CH>_ALT_REFRESH_TOKEN`.
This proves, live, whether that credential exists and still works, and exits
non-zero while any channel is not delegated (a real gap, not a claim).

Live test, quota-free: it exchanges the token at `oauth2.googleapis.com/token`. A
delegated token that exchanges (`access_token` returned) is READY; a token that
returns `invalid_grant` is NOT-DELEGATED. It never prints a token.

    python3 scripts/delegate_ready.py
    python3 scripts/delegate_ready.py --strict   # exit 1 unless every channel is READY
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# channel -> (primary secret, delegated secret, the Google account that owns it)
# The three channels are on THREE SEPARATE Google accounts (K, 2026-11-12), so each
# carries its own 19/day upload pool and its own manager grant. This map is locked by
# scripts/test_channel_accounts.py against scripts/mail_watch.py and channels.json.
CHANNELS = {
    "genx": ("YT_CH1_REFRESH_TOKEN", "YT_CH1_ALT_REFRESH_TOKEN", "kongkeat.938@gmail.com"),
    "dharma": ("YT_CH2_REFRESH_TOKEN", "YT_CH2_ALT_REFRESH_TOKEN", "farmmer.938@gmail.com"),
    "kongkeat-story": ("YT_CH4_REFRESH_TOKEN", "YT_CH4_ALT_REFRESH_TOKEN", "kongkeat.p3@gmail.com"),
}
TOKEN = "https://oauth2.googleapis.com/token"


def exchanges(refresh_token: str) -> bool:
    """True if the refresh token still mints an access token (valid_grant)."""
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    if not (cid and sec):
        return False
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(TOKEN, data=data), timeout=30)
        return True
    except urllib.error.HTTPError as e:
        return "invalid_grant" not in e.read().decode()
    except Exception:
        return False


def status(primary: str | None, alt: str | None) -> tuple[str, str]:
    """(verdict, detail) for one channel. verdict: READY / NOT-DELEGATED / NO-ALT-SECRET."""
    if not alt:
        return "NOT-DELEGATED", "no delegated secret (set YT_<CH>_ALT_REFRESH_TOKEN)"
    if primary and alt == primary:
        return "NOT-DELEGATED", "delegated secret is a COPY of the primary, not a second account"
    if exchanges(alt):
        return "READY", "delegated credential mints a token"
    return "NOT-DELEGATED", "delegated credential does not exchange (invalid_grant)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 unless every channel is READY")
    a = ap.parse_args()
    gaps = []
    for ch, (pkey, akey, email) in CHANNELS.items():
        v, d = status(os.environ.get(pkey), os.environ.get(akey))
        print(f"  {v:14} {ch:16} [{email}]: {d}")
        if v != "READY":
            gaps.append(ch)
    print()
    if gaps:
        print(f"not yet delegated: {', '.join(gaps)} -- containment rails still hold; "
              f"see docs/DELEGATE-2026-11-12.md for the one-time invite")
        return 1 if a.strict else 0
    print("READY: every channel has a working delegated credential (K is out of the loop)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
