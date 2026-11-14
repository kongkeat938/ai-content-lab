#!/usr/bin/env python3
"""ak's own mailbox -- a free account ak owns, so a signup never needs K's email.

K (2026-11-13): ak forgot it had its own profile/mailbox. The old one lived only in the
`ax-workspace` repo and a PC1 vault that is now dead. This script keeps ak's mailbox in the
OpenHands **KV vault** (account-scoped, survives a sandbox recycle) and reads it headlessly.

    python3 scripts/ak_mail.py new       # create a fresh ak mailbox and store it
    python3 scripts/ak_mail.py show      # print the stored address (never the password)
    python3 scripts/ak_mail.py inbox     # list messages
    python3 scripts/ak_mail.py read ID   # read one message (verification links)

**Every tool and every agent in the team uses its OWN mailbox** (K, 2026-11-14: "ต่อไปเครื่องมือ
ทุกอย่างใช้เมล์ตัวเองล็อกอินเลย รวมถึง agent ในทีมด้วย ไม่ต้องใช้เมล์ K แล้ว"). The mailbox
lives under a per-identity vault key (`ak.identity.mailbox`, `ak.identity.mail.<role>`), so a
signup by a worker never touches K's address:

    python3 scripts/ak_mail.py new --as researcher   # the researcher worker's own mailbox
    python3 scripts/ak_mail.py show --as critic

A store that fails MUST fail loudly. Measured 2026-11-14: `new` created an address at the
provider but the vault write failed (a 400 on the wrong automation anchor) and the command
still exited 0 -- so the mailbox existed but was never recorded, and the next session read
"no ak mailbox in the vault". That silent partial write is why ak kept "forgetting" its own
mailbox. `cmd_new` now exits 1 if the vault write does not verify.

Provider: mail.tm (domain fldubai.com). Measured 2026-11-13 from the pod: create 201,
token 200, read 200 -- but `POST /token` can 401 for a few seconds right after create, and
the token body is longer than a small read buffer, so we read the whole body and retry.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request

API = "https://api.mail.tm"
VAULT_ANCHOR = "94068e1c-c98c-4f3b-96f5-0df4a1e9a78a"
VAULT_KEY = "ak.identity.mailbox"
DOMAIN = "fldubai.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0 Safari/537.36",
      "Accept": "application/json", "Content-Type": "application/json"}


def _roster() -> list[str]:
    """Every identity that must own a mailbox: `ak` plus every worker in the team.
    Read from team.py so a new worker is never silently missing a mailbox (the
    `.get()+continue` trap that once emptied the panel)."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import team  # noqa: PLC0415
        roles = list(team.TEAM)
    except Exception:                                   # noqa: BLE001
        roles = []
    return ["ak"] + roles


ROSTER = _roster()


def _req(url: str, data=None, method=None, token=None) -> tuple[int, str]:
    headers = dict(UA)
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url, data=json.dumps(data).encode() if data is not None else None,
        headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=25)
        return r.status, r.read().decode()          # full body: the token is long
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:                          # noqa: BLE001 - surface any failure
        return 0, str(e)


def _vault_key(identity: str) -> str:
    """The vault key for an identity. `ak` keeps the historical key (already in the vault);
    every worker gets its own, so a worker's signup never shares ak's address."""
    if identity in ("", "ak"):
        return VAULT_KEY
    return f"ak.identity.mail.{identity}"


def _vault(method: str, value: dict | None = None,
           identity: str = "ak", retries: int = 3) -> dict | None:
    key = os.environ.get("OPENHANDS_API_KEY") or os.environ.get("KONGKEAT_OH_KEY")
    if not key:
        return None
    vk = _vault_key(identity)
    url = f"https://app.all-hands.dev/api/automation/v1/kv/{vk}?automation_id={VAULT_ANCHOR}"
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    body = json.dumps({"value": json.dumps(value)}).encode() if value is not None else None
    # A write can fail transiently; retry so a blip does not silently lose the mailbox.
    # The caller still checks the result: a store that fails MUST fail loudly.
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            r = urllib.request.urlopen(req, timeout=25)
            raw = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == retries - 1:
                print(f"vault {method} failed: {e.code} {e.read().decode()[:160]}")
                return None
            time.sleep(2)
            continue
        except Exception as e:                          # noqa: BLE001
            if attempt == retries - 1:
                print(f"vault {method} failed: {e}")
                return None
            time.sleep(2)
            continue
        v = raw.get("value")
        if isinstance(v, dict) and "value" in v:        # GET wraps once
            v = v["value"]
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                pass
        return v if isinstance(v, dict) else None
    return None


def _new_account() -> dict:
    for _ in range(3):
        addr = f"akmail{secrets.token_hex(3)}@{DOMAIN}"
        pw = "Ak-" + secrets.token_urlsafe(14)
        status, body = _req(f"{API}/accounts", {"address": addr, "password": pw}, "POST")
        if status != 201:
            continue
        for _ in range(5):
            s2, b2 = _req(f"{API}/token", {"address": addr, "password": pw}, "POST")
            if s2 == 200:
                return {"address": addr, "password": pw, "provider": "mail.tm",
                        "note": "ak's own mailbox; recreate if purged"}
            time.sleep(4)
    raise SystemExit("FAIL: could not create a mail.tm mailbox (provider or IP)")


def _token_for(acct: dict) -> str | None:
    for _ in range(5):
        s, b = _req(f"{API}/token",
                    {"address": acct["address"], "password": acct["password"]}, "POST")
        if s == 200:
            return json.loads(b)["token"]
        time.sleep(4)
    return None


def cmd_new(args) -> int:
    identity = getattr(args, "as_", "ak") or "ak"
    acct = _new_account()
    stored = _vault("PUT", acct, identity=identity)
    if not stored:
        # A created address that was never recorded is exactly the silent partial write
        # that made ak "forget" its mailbox. Fail loudly instead of exiting 0.
        print(f"FAIL: created {acct['address']} at the provider but the vault write "
              f"failed -- the mailbox would be lost. Nothing was recorded.", file=sys.stderr)
        return 1
    print(f"created {identity} mailbox: {acct['address']}  (stored in vault: {bool(stored)})")
    return 0


def cmd_show(args) -> int:
    identity = getattr(args, "as_", "ak") or "ak"
    acct = _vault("GET", identity=identity)
    if not acct:
        print(f"no {identity} mailbox in the vault -- run: "
              f"python3 scripts/ak_mail.py new --as {identity}")
        return 1
    print(acct["address"])
    return 0


def cmd_roster(_args) -> int:
    """Print every identity's mailbox address (never a password), so it is visible
    that each tool/agent has its own -- and none is K's."""
    for identity in ROSTER:
        acct = _vault("GET", identity=identity)
        addr = acct.get("address") if acct else "(none -- run: ak_mail.py new --as %s)" % identity
        print(f"  {identity:13} {addr}")
    return 0


def cmd_inbox(args) -> int:
    identity = getattr(args, "as_", "ak") or "ak"
    acct = _vault("GET", identity=identity)
    if not acct:
        print(f"no {identity} mailbox in the vault -- run: "
              f"python3 scripts/ak_mail.py new --as {identity}")
        return 1
    tok = _token_for(acct)
    if not tok:
        print("FAIL: could not get a token")
        return 1
    s, b = _req(f"{API}/messages", token=tok)
    if s != 200:
        print(f"FAIL: inbox {s} {b[:120]}")
        return 1
    msgs = json.loads(b)
    print(f"{len(msgs)} message(s) in {acct['address']}")
    for m in msgs:
        print(f"  {m.get('id')}  {m.get('from',{}).get('address','?')}  {m.get('subject','')}")
    return 0


def cmd_read(args) -> int:
    identity = getattr(args, "as_", "ak") or "ak"
    acct = _vault("GET", identity=identity)
    if not acct:
        print(f"no {identity} mailbox in the vault")
        return 1
    tok = _token_for(acct)
    if not tok:
        print("FAIL: could not get a token")
        return 1
    s, b = _req(f"{API}/messages/{args.id}", token=tok)
    if s != 200:
        print(f"FAIL: read {s} {b[:120]}")
        return 1
    m = json.loads(b)
    print("Subject:", m.get("subject"))
    print("From   :", m.get("from", {}).get("address"))
    print("---")
    print(m.get("text") or m.get("html") or "")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ak's own mailbox")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("new", "show", "inbox", "roster"):
        p = sub.add_parser(name)
        p.set_defaults(fn=globals()["cmd_" + name])
        if name != "roster":
            p.add_argument("--as", dest="as_", default="ak",
                           help="the identity whose mailbox to use (default ak)")
    r = sub.add_parser("read")
    r.add_argument("id")
    r.add_argument("--as", dest="as_", default="ak")
    r.set_defaults(fn=cmd_read)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
