#!/usr/bin/env python3
"""--manual-code must refuse a pasted callback it cannot verify.

Three refusals (wrong state, no state, no code) and one pass-through. The
pass-through matters: a guard that refuses everything would also look green.

    python3 scripts/test_yt_auth_state.py
"""
from __future__ import annotations

import builtins
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import yt_auth  # noqa: E402
from google_auth_oauthlib.flow import Flow  # noqa: E402

CLIENT = {
    "client_id": "cid",
    "client_secret": "csec",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["https://example.invalid/oauth2callback"],
}
REDIRECT = CLIENT["redirect_uris"][0]


class ExchangeAttempted(RuntimeError):
    pass


def run(pasted: str, pending_state: str = "GOOD") -> dict:
    """Drive main() with --manual-code and report what it did."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "yt_pending.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"state": pending_state, "redirect_uri": REDIRECT,
                   "code_verifier": "v"}, fh)

    calls: list[str] = []
    seen: dict = {}

    def fake_fetch(self, code=None, **kw):
        calls.append(code)
        raise ExchangeAttempted()

    saved = (yt_auth.PENDING_PATH, yt_auth.load_client_secrets,
             sys.argv, builtins.input, Flow.fetch_token,
             yt_auth.secrets.token_urlsafe)
    try:
        yt_auth.PENDING_PATH = path
        yt_auth.load_client_secrets = lambda *a, **k: dict(CLIENT)
        sys.argv = ["yt_auth.py", "--scopes", "force-ssl", "--manual-code",
                    "--redirect-uri", REDIRECT]
        builtins.input = lambda prompt="": pasted
        Flow.fetch_token = fake_fetch
        # main() mints the state at URL time and compares against that same
        # value, so pin it: the pasted state has to be this one to pass.
        yt_auth.secrets.token_urlsafe = lambda n=16: "GOOD"
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                yt_auth.main()
            seen["exit"] = 0
        except SystemExit as exc:
            seen["exit"] = exc.code if exc.code not in (None, 0) else 0
        except ExchangeAttempted:
            seen["exit"] = "exchanged"
    finally:
        (yt_auth.PENDING_PATH, yt_auth.load_client_secrets,
         sys.argv, builtins.input, Flow.fetch_token,
         yt_auth.secrets.token_urlsafe) = saved

    seen["calls"] = calls
    seen["said"] = buf.getvalue() + (str(seen["exit"]) if isinstance(seen["exit"], str)
                                     else "")
    return seen


CHECKS = [
    ("state ผิด",
     f"{REDIRECT}?code=abc&state=WRONG", "GOOD", "State mismatch"),
    ("state ไม่มี",
     f"{REDIRECT}?code=abc", "GOOD", "No ?state="),
    ("code ไม่มี",
     f"{REDIRECT}?state=GOOD", "GOOD", "No ?code="),
]


def main() -> int:
    bad = 0
    for name, pasted, pending, expect in CHECKS:
        got = run(pasted, pending)
        refused = got["exit"] != 0 and got["exit"] != "exchanged"
        quiet = not got["calls"]
        said = expect in got["said"]
        ok = refused and quiet and said
        print(f"{'PASS' if ok else 'FAIL'} {name}: exit={got['exit']!r} "
              f"exchanged={bool(got['calls'])} said_expect={said}")
        bad += 0 if ok else 1

    got = run(f"{REDIRECT}?code=abc&state=GOOD", "GOOD")
    ok = got["exit"] == "exchanged" and got["calls"] == ["abc"]
    print(f"{'PASS' if ok else 'FAIL'} state ถูก: exit={got['exit']!r} "
          f"exchanged={got['calls']}")
    bad += 0 if ok else 1

    print("3 refusals + 1 pass-through" if not bad else f"{bad} check(s) failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
