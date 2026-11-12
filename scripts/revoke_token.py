#!/usr/bin/env python3
"""Revoke a channel's OAuth grant -- the one decisive cut that needs no account.

Measured 2026-11-12: a SECOND uploader posts clips our repo has no code for
(`en-US`, category 27, old brand) at a fixed `:21` minute on all three channels.
Two independent advisor panels (the fast team, and OpenHands Cloud) agree the
source is a credential held outside these rails -- an old server, a Zapier/Make/
Buffer hook, or a leaked copy of our refresh token -- and the only cut that kills
it without the account owner is `oauth2.googleapis.com/revoke` on that grant.

A refresh token IS the credential: revoking it kills every access token minted
from it, so the uploader's stored token dies within the hour. This revokes OUR
token, so it also stops our own rails for that channel until a new consent is
granted -- which is a browser step only the account owner can do (Google grants
a token to a person, not to an API). The tool therefore defaults to a DRY RUN and
needs `--confirm` to fire, and it never prints the token.

    python3 scripts/revoke_token.py --channel genx              # show what it would cut
    python3 scripts/revoke_token.py --channel genx --confirm    # revoke, then verify
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# The active channels and the secret that holds each refresh token. Same shape the
# other rails use (scripts/analyze_reach.py, publish_shorts.py, ...).
CHANNELS = {
    "genx": "YT_CH1_REFRESH_TOKEN",
    "dharma": "YT_CH2_REFRESH_TOKEN",
    "kongkeat-story": "YT_CH4_REFRESH_TOKEN",
}
REVOKE = "https://oauth2.googleapis.com/revoke"
TOKEN = "https://oauth2.googleapis.com/token"


def revoke(token: str) -> tuple[bool, str]:
    """POST the token to Google's revoke endpoint. Returns (ok, detail)."""
    data = urllib.parse.urlencode({"token": token}).encode()
    req = urllib.request.Request(REVOKE, data=data, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # 400 invalid_token = already dead, which is the outcome we want.
        return False, f"HTTP {e.code} {e.read().decode()[:80]}"


def still_alive(slug: str, token: str) -> bool:
    """Exchange the refresh token; alive = the grant still works."""
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    if not (cid and sec):
        return True  # cannot test: assume alive so we never claim a false stop
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": token, "grant_type": "refresh_token"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(TOKEN, data=data), timeout=30)
        return True
    except urllib.error.HTTPError as e:
        return "invalid_grant" not in e.read().decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, choices=sorted(CHANNELS))
    ap.add_argument("--confirm", action="store_true",
                    help="actually revoke; without it this is a dry run")
    a = ap.parse_args()

    env_key = CHANNELS[a.channel]
    token = os.environ.get(env_key)
    if not token:
        print(f"no token in {env_key}; nothing to revoke for {a.channel}")
        return 1

    alive = still_alive(a.channel, token)
    print(f"{a.channel}: grant is {'ALIVE' if alive else 'already dead'} "
          f"(token from {env_key}, {len(token)} chars, not printed)")
    if not alive:
        print("already revoked -- the rogue cannot be riding this token")
        return 0
    if not a.confirm:
        print("DRY RUN: re-run with --confirm to revoke. This also stops our own "
              "rails for this channel until the owner re-consents in a browser.")
        return 0

    ok, detail = revoke(token)
    print(f"revoke -> {detail}")
    dead = not still_alive(a.channel, token)
    print(f"verify: token now {'DEAD (invalid_grant)' if dead else 'STILL ALIVE'}")
    if not dead:
        print("NOTE: the rogue holds its OWN grant -- revoking ours does not reach it. "
              "Only the owner's browser (myaccount.google.com -> third-party access) "
              "or a GCP client-secret rotation can stop that.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
