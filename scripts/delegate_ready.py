#!/usr/bin/env python3
"""Is a channel ready to be run WITHOUT K? Measure the delegated credential.

K chose B (2026-11-12): add a second account as manager so the team can cut a rogue
grant without him. The team-side half of B is a **delegated** refresh token -- one
minted while signed in as the second account, held in `YT_<CH>_ALT_REFRESH_TOKEN`.

`READY` has two legs, and both are measured live:

  1. the credential **exchanges** (quota-free call to `oauth2.googleapis.com/token`), and
  2. it can **upload** -- proven by a probe: insert a ~1.4 KB private video, then delete
     it in the same run. Measured 2026-11-13: a token that exchanges can still answer
     `uploadLimitExceeded`, so "it mints a token" is NOT "it can publish" -- a channel
     that only exchanges reads as LIMITED, not READY, and never as a false pass.

A probe is skipped (leg 2 not asserted) when no channel id is given, so the pure
exchange check still works offline. It never prints a token.

    python3 scripts/delegate_ready.py
    python3 scripts/delegate_ready.py --strict   # exit 1 unless every channel is READY
    python3 scripts/delegate_ready.py --no-probe  # exchange only, no write to YouTube
"""
from __future__ import annotations

import argparse
import base64
import io
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

# The channel each delegated credential must actually be able to publish to. A token
# can exchange and still be unable to upload, so the probe needs a target to prove it.
CHANNEL_IDS = {
    "genx": "UCI6EfsgM1HNjrYarvigxyrQ",
    "dharma": "UCM3QO5L_pmj34n1JVlbhh-w",
    "kongkeat-story": "UC7gCIu4G_7QCEJ8hJ-34zoQ",
}
TOKEN = "https://oauth2.googleapis.com/token"

# A ~1.4 KB black 16x16 clip, kept as base64 so the probe needs no file on disk. Tiny on
# purpose: the probe spends one upload slot and is deleted in the same run.
PROBE_B64 = (
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAMObW9vdgAAAGxtdmhkAAAAAAAAAAAA"
    "AAAAAAAD6AAAAMgAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAA"
    "AABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAjl0cmFrAAAAXHRraGQAAAADAAAA"
    "AAAAAAAAAAABAAAAAAAAAMgAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAA"
    "AAAAAAAAAABAAAAAABAAAAAQAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAADIAAAAAAABAAAA"
    "AAGxbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAoAAAACABVxAAAAAAALWhkbHIAAAAAAAAAAHZp"
    "ZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABXG1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAA"
    "ACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAARxzdGJsAAAAuHN0c2QAAAAAAAAA"
    "AQAAAKhhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAABAAEABIAAAASAAAAAAAAAABFUxhdmM2"
    "MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAALmF2Y0MBQsAK/+EAFmdCwArZHsBEAAAD"
    "AAQAAAMAKDxImSABAAVoy4PLIAAAABBwYXNwAAAAAQAAAAEAAAAUYnRydAAAAAAAAGRQAAAAAAAA"
    "ABhzdHRzAAAAAAAAAAEAAAABAAAIAAAAABxzdHNjAAAAAAAAAAEAAAABAAAAAQAAAAEAAAAUc3Rz"
    "egAAAAAAAAKCAAAAAQAAABRzdGNvAAAAAAAAAAEAAAM+AAAAYXVkdGEAAABZbWV0YQAAAAAAAAAh"
    "aGRscgAAAAAAAAAAbWRpcmFwcGwAAAAAAAAAAAAAAAAsaWxzdAAAACSpdG9vAAAAHGRhdGEAAAAB"
    "AAAAAExhdmY2MS43LjEwMwAAAAhmcmVlAAACim1kYXQAAAJwBgX//2zcRem95tlIt5Ys2CDZI+7v"
    "eDI2NCAtIGNvcmUgMTY0IHIzMTA4IDMxZTE5ZjkgLSBILjI2NC9NUEVHLTQgQVZDIGNvZGVjIC0g"
    "Q29weWxlZnQgMjAwMy0yMDIzIC0gaHR0cDovL3d3dy52aWRlb2xhbi5vcmcveDI2NC5odG1sIC0g"
    "b3B0aW9uczogY2FiYWM9MCByZWY9MyBkZWJsb2NrPTE6MDowIGFuYWx5c2U9MHgxOjB4MTExIG1l"
    "PWhleCBzdWJtZT03IHBzeT0xIHBzeV9yZD0xLjAwOjAuMDAgbWl4ZWRfcmVmPTEgbWVfcmFuZ2U9"
    "MTYgY2hyb21hX21lPTEgdHJlbGxpcz0xIDh4OGRjdD0wIGNxbT0wIGRlYWR6b25lPTIxLDExIGZh"
    "c3RfcHNraXA9MSBjaHJvbWFfcXBfb2Zmc2V0PS0yIHRocmVhZHM9MSBsb29rYWhlYWRfdGhyZWFk"
    "cz0xIHNsaWNlZF90aHJlYWRzPTAgbnI9MCBkZWNpbWF0ZT0xIGludGVybGFjZWQ9MCBibHVyYXlf"
    "Y29tcGF0PTAgY29uc3RyYWluZWRfaW50cmE9MCBiZnJhbWVzPTAgd2VpZ2h0cD0wIGtleWludD0y"
    "NTAga2V5aW50X21pbj01IHNjZW5lY3V0PTQwIGludHJhX3JlZnJlc2g9MCByY19sb29rYWhlYWQ9"
    "NDAgcmM9Y3JmIG1idHJlZT0xIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBx"
    "cHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTE6MS4wMACAAAAACmWIhA/yYoAAw+4="
)



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

    Kept as the single seam the guard patches: a token bound to a different client
    answers `unauthorized_client`, which is not a working credential.
    """
    return mint_access_token(refresh_token, [client] if client else clients_for_alt()) is not None


def mint_access_token(refresh_token: str, clients: list[tuple[str, str]]) -> str | None:
    """The access token the delegated credential mints, or None if no client works."""
    for cid, sec in clients:
        data = urllib.parse.urlencode({
            "client_id": cid, "client_secret": sec,
            "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(TOKEN, data=data), timeout=30) as fh:
                tok = json.loads(fh.read().decode()).get("access_token")
            if tok:
                return tok
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue
    return None


def whoami(access_token: str) -> str:
    """The channel this token actually owns -- identity of the delegated account."""
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req, timeout=30) as fh:
            items = json.loads(fh.read().decode()).get("items", [])
        if items:
            return f"{items[0]['snippet']['title']} ({items[0]['id']})"
    except Exception:
        pass
    return "unknown"


def probe_upload(access_token: str) -> tuple[bool, str]:
    """Insert a tiny private video and delete it. (upload_ok, detail).

    This is the leg that `exchanges` cannot see: a delegated credential can mint a
    token and still be refused by `videos.insert` (measured 2026-11-13:
    `uploadLimitExceeded`). A probe is the only honest way to say "it can publish".
    """
    boundary = "akprobe"
    meta = json.dumps({"snippet": {"title": "ak delegation probe (auto-deleted)",
                                   "categoryId": "22"},
                       "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}})
    body = io.BytesIO()
    body.write(f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode())
    body.write(meta.encode())
    body.write(f"\r\n--{boundary}\r\nContent-Type: video/mp4\r\n\r\n".encode())
    body.write(base64.b64decode(PROBE_B64))
    body.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
        data=body.getvalue(),
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": f"multipart/related; boundary={boundary}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as fh:
            vid = json.loads(fh.read().decode()).get("id")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        reason = msg = ""
        try:
            err = json.loads(detail)["error"]
            reason = err["errors"][0].get("reason", "")
            msg = err.get("message", "")
        except Exception:
            msg = detail[:120].replace("\n", " ")
        return False, f"upload refused ({e.code} {reason}: {msg[:120]})"
    except Exception as e:
        return False, f"upload error ({type(e).__name__})"
    if not vid:
        return False, "upload returned no video id"
    # delete it in the same run; the probe must not leave a clip behind.
    try:
        dreq = urllib.request.Request(
            f"https://www.googleapis.com/youtube/v3/videos?id={vid}", method="DELETE",
            headers={"Authorization": f"Bearer {access_token}"})
        urllib.request.urlopen(dreq, timeout=60)
        return True, f"probe upload+delete ok ({vid})"
    except Exception as e:
        return True, f"probe uploaded {vid} but delete failed ({type(e).__name__})"


def status(primary: str | None, alt: str | None,
           clients: list[tuple[str, str]] | None = None,
           channel_id: str | None = None) -> tuple[str, str]:
    """(verdict, detail). verdict: READY / LIMITED / NOT-DELEGATED.

    READY requires BOTH legs when a channel_id is given: the credential exchanges AND a
    probe upload succeeds. With no channel_id only the exchange is checked, and the best
    verdict is LIMITED -- never READY, because upload capability was not measured.
    """
    if not alt:
        return "NOT-DELEGATED", "no delegated secret (set YT_<CH>_ALT_REFRESH_TOKEN)"
    if primary and alt == primary:
        return "NOT-DELEGATED", "delegated secret is a COPY of the primary, not a second account"
    cls = clients if clients is not None else clients_for_alt()
    token = mint_access_token(alt, cls)
    if not token:
        return "NOT-DELEGATED", "delegated credential does not exchange (invalid_grant or wrong client)"
    if channel_id is None:
        return "LIMITED", "credential exchanges; upload not probed (pass a channel id to prove it)"
    ident = whoami(token)
    ok, detail = probe_upload(token)
    return ("READY" if ok else "LIMITED"), f"[{ident}] {detail}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 unless every channel is READY")
    ap.add_argument("--no-probe", action="store_true",
                    help="exchange only; do not write a probe video to YouTube")
    a = ap.parse_args()
    gaps = []
    upload_blocked = False
    for ch, (pkey, akey, email) in CHANNELS.items():
        ch_id = None if a.no_probe else CHANNEL_IDS.get(ch)
        v, d = status(os.environ.get(pkey), os.environ.get(akey), channel_id=ch_id)
        print(f"  {v:14} {ch:16} [{email}]: {d}")
        if "uploadLimitExceeded" in d:
            upload_blocked = True
        if v != "READY":
            gaps.append(ch)
    print()
    if upload_blocked:
        # The block is on the delegate's OWN account, not our code: name the fix instead
        # of leaving a bare failure, so the next reader knows what to do.
        print("HINT: the delegate's own account has reached its upload allowance. Verify that "
              "exact account at https://www.youtube.com/verify (phone) or wait out the daily cap.")
    if gaps:
        print(f"not READY: {', '.join(gaps)} -- containment rails still hold; "
              f"see docs/DELEGATE-2026-11-12.md")
        return 1 if a.strict else 0
    print("READY: every channel has a working delegated credential that can publish (K is out of the loop)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
