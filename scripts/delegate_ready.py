#!/usr/bin/env python3
"""Is a channel ready to be run WITHOUT K? Measure the delegated credential.

K chose B (2026-11-12): add a second account as manager so the team can cut a rogue
grant without him. The team-side half of B is a **delegated** refresh token -- one
minted while signed in as the second account, held in `YT_<CH>_ALT_REFRESH_TOKEN`.
This proves, live, whether that credential exists and still works, and exits
non-zero while any channel is not delegated (a real gap, not a claim).

Live test, quota-free: it exchanges the token at `oauth2.googleapis.com/token`. A
delegated token that returns an `access_token` is READY; anything else -- including
the `unauthorized_client` a token bound to a *different* OAuth client answers -- is
NOT-DELEGATED. It never prints a token.

A delegated token is bound to the OAuth client that minted it, and a second account
was authorised on its own client, so the alt token is exchanged with
`YT_ALT_CLIENT_ID`/`YT_ALT_CLIENT_SECRET` when set, then with the primary client.
Either success is READY; a mismatch is never read as READY.

    python3 scripts/delegate_ready.py
    python3 scripts/delegate_ready.py --strict   # exit 1 unless every channel is READY
"""
from __future__ import annotations

import argparse
import json
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


def _client(cid_key: str, sec_key: str) -> tuple[str, str] | None:
    cid = os.environ.get(cid_key)
    sec = os.environ.get(sec_key)
    return (cid, sec) if (cid and sec) else None


def clients_for_alt() -> list[tuple[str, str]]:
    """The clients a delegated token may have been minted under, most specific first.

    A token is bound to the client that minted it, so a second account authorised on
    its own client cannot be checked with the primary client. Try the alt client,
    then the primary, so either arrangement verifies.
    """
    out = []
    for pair in (_client("YT_ALT_CLIENT_ID", "YT_ALT_CLIENT_SECRET"),
                 _client("YT_CLIENT_ID", "YT_CLIENT_SECRET")):
        if pair and pair not in out:
            out.append(pair)
    return out


def exchanges(refresh_token: str, client: tuple[str, str] | None = None) -> bool:
    """True only if the refresh token mints an access token under `client`.

    A token bound to a different client answers `unauthorized_client`; that is not a
    working credential, so it must not be read as one.
    """
    cid, sec = client or (os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"))
    if not (cid and sec):
        return False
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN, data=data), timeout=30) as fh:
            return bool(json.loads(fh.read().decode()).get("access_token"))
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def status(primary: str | None, alt: str | None,
           clients: list[tuple[str, str]] | None = None) -> tuple[str, str]:
    """(verdict, detail) for one channel. verdict: READY / NOT-DELEGATED."""
    if not alt:
        return "NOT-DELEGATED", "no delegated secret (set YT_<CH>_ALT_REFRESH_TOKEN)"
    if primary and alt == primary:
        return "NOT-DELEGATED", "delegated secret is a COPY of the primary, not a second account"
    for client in (clients if clients is not None else clients_for_alt()):
        if exchanges(alt, client):
            return "READY", "delegated credential mints a token"
    return "NOT-DELEGATED", "delegated credential does not exchange (invalid_grant or wrong client)"


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
