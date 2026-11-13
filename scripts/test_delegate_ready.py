#!/usr/bin/env python3
"""The delegation check must FAIL honestly: a copy of the primary is NOT delegation,
and a credential that mints a token is NOT a credential that can publish.

K chose B (2026-11-12): a second account as manager, so the team can act without him.
A "delegated" secret that is really the primary copied across is not a second account --
it is the same grant wearing a new name, and it proves nothing.

Measured 2026-11-13: a delegated token can exchange and still be refused by
`videos.insert` (`uploadLimitExceeded`). So READY has two legs -- it exchanges AND a
probe upload succeeds -- and a channel that only exchanges must read LIMITED, never a
false READY. A token is also bound to the OAuth client that minted it, so it must be
exchanged with *that* client; a wrong client answers `unauthorized_client`, which must
never read as READY.

    python3 scripts/test_delegate_ready.py
"""
from __future__ import annotations

import base64
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
    real_mint, real_probe = dr.mint_access_token, dr.probe_upload
    # Default: the token mints and the probe uploads. A case flips exactly one leg, so a
    # failure can only come from the leg under test.
    dr.mint_access_token = lambda tok, cls: "access-token"
    dr.probe_upload = lambda tok: (True, "probe ok")
    try:
        print("no delegated secret is a real gap")
        check("missing alt -> NOT-DELEGATED", dr.status("P", None)[0] == "NOT-DELEGATED")

        print("a copy of the primary is NOT a delegation (the guard can fail)")
        v, _ = dr.status("SAME", "SAME")
        check("alt == primary -> NOT-DELEGATED", v == "NOT-DELEGATED", v)

        print("a broken delegated token is NOT-DELEGATED, never a false READY")
        dr.mint_access_token = lambda tok, cls: None
        check("unexchangeable alt -> NOT-DELEGATED",
              dr.status("primary", "alt", channel_id="UCx")[0] == "NOT-DELEGATED")

        print("exchange alone is NOT READY -- upload capability must be measured")
        dr.mint_access_token = lambda tok, cls: "access-token"
        v, _ = dr.status("primary", "alt", channel_id=None)
        check("exchange without a probe -> LIMITED", v == "LIMITED", v)

        print("a token that mints but cannot upload is LIMITED (the bug this fix removes)")
        dr.probe_upload = lambda tok: (False, "upload refused (403 uploadLimitExceeded)")
        v, d = dr.status("primary", "alt", channel_id="UCx")
        check("exchange + failed probe -> LIMITED", v == "LIMITED", v)
        check("the failure reason is surfaced", "uploadLimitExceeded" in d, d)

        print("exchange + a successful probe is READY")
        dr.probe_upload = lambda tok: (True, "probe ok")
        check("both legs ok -> READY",
              dr.status("primary", "alt", channel_id="UCx")[0] == "READY")

        print("a token is checked with its OWN client, not only the primary (the guard can fail)")
        # The token works only under client B; a checker that tried only the primary client
        # A would answer NOT-DELEGATED. Trying both is what makes this honest.
        client_a, client_b = ("id-a", "sec-a"), ("id-b", "sec-b")
        dr.mint_access_token = lambda tok, cls: "tok" if client_b in cls else None
        check("matching client -> READY",
              dr.status("primary", "alt", clients=[client_a, client_b], channel_id="UCx")[0] == "READY")
        check("primary client only -> NOT-DELEGATED",
              dr.status("primary", "alt", clients=[client_a], channel_id="UCx")[0] == "NOT-DELEGATED")

        print("the three active channels are mapped")
        check("genx/dharma/kongkeat-story present",
              set(dr.CHANNELS) == {"genx", "dharma", "kongkeat-story"})
        check("every channel has a probe target id",
              set(dr.CHANNEL_IDS) == set(dr.CHANNELS))

        print("the probe clip is a real, tiny mp4")
        raw = base64.b64decode(dr.PROBE_B64)
        check("probe decodes to an mp4", raw[4:8] == b"ftyp" and 500 < len(raw) < 20000,
              f"{len(raw)} bytes")
    finally:
        dr.mint_access_token, dr.probe_upload = real_mint, real_probe

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: delegation readiness cannot be faked by a copy, and cannot pass without an upload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
