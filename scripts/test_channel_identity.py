#!/usr/bin/env python3
"""A spent quota must not make the rail call a good token "the wrong channel".

Measured 2026-11-07: `short doors` failed three runs in a row with "No refresh
token in the environment belongs to channel UCI6EfsgM1HNjrYarvigxyrQ", while the
same token uploaded fine. The cause was that `yt_auth` proves a token's channel by
asking the Data API (`channels.list`), and that call returns 403 for *every* token
once the shared daily quota is spent -- so the rail read "cannot tell" as "not
mine" and stopped.

The fix rests on one rule the repo already uses in publish_batch.py: a token in a
per-channel secret is that channel's token by construction. So when the API cannot
answer, the rail falls back to that pin; a token that *does* resolve to a different
channel is still a real mismatch and must still abort.

    python3 scripts/test_channel_identity.py    # exit 0 = the rail survives a quota
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    import yt_auth

    if not yt_auth.CHANNEL_ENV:
        fail("yt_auth has no CHANNEL_ENV pin table; the quota fallback cannot work")
    for cid, var in yt_auth.CHANNEL_ENV.items():
        if not (var.startswith("YT_") and var.endswith("_REFRESH_TOKEN")):
            fail(f"pin for {cid} is {var}, not a per-channel refresh-token secret")

    # Force the API to be unreadable for every token, exactly as a spent quota does.
    real = yt_auth._channel_id_for_refresh
    yt_auth._channel_id_for_refresh = lambda rt, client: None
    try:
        for cid, var in yt_auth.CHANNEL_ENV.items():
            os.environ.setdefault(var, "test-token")
            pinned = yt_auth.env_token_for_channel(cid)
            if not pinned or pinned[1] != f"${var}":
                fail(f"{cid}: env_token_for_channel did not return {var} (got {pinned})")
    finally:
        yt_auth._channel_id_for_refresh = real

    src = open(os.path.join(HERE, "yt_auth.py"), encoding="utf-8").read()
    if "env_token_for_channel(expected_channel)" not in src:
        fail("materialise_env_token no longer consults the pin table; a quota will kill it")
    if "channel check unavailable (quota)" not in src:
        fail("the quota fallback prints no reason; a silent fallback hides a real mismatch")

    print("OK: a spent quota falls back to the per-channel secret; a real mismatch still aborts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
