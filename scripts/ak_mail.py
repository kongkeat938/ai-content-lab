#!/usr/bin/env python3
"""ak's own mailbox -- a free account ak owns, so a signup never needs K's email.

K (2026-11-13): ak forgot it had its own profile/mailbox. The old one lived only in the
`ax-workspace` repo and a PC1 vault that is now dead. This script keeps ak's mailbox in the
OpenHands **KV vault** (account-scoped, survives a sandbox recycle) and reads it headlessly.

    python3 scripts/ak_mail.py new       # create a fresh ak mailbox and store it
    python3 scripts/ak_mail.py show      # print the stored address (never the password)
    python3 scripts/ak_mail.py inbox     # list messages
    python3 scripts/ak_mail.py read ID   # read one message (verification links)

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


def _vault(method: str, value: dict | None = None) -> dict | None:
    key = os.environ.get("OPENHANDS_API_KEY") or os.environ.get("KONGKEAT_OH_KEY")
    if not key:
        return None
    url = f"https://app.all-hands.dev/api/automation/v1/kv/{VAULT_KEY}?automation_id={VAULT_ANCHOR}"
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    body = json.dumps({"value": json.dumps(value)}).encode() if value is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        r = urllib.request.urlopen(req, timeout=25)
        raw = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"vault {method} failed: {e.code}")
        return None
    except Exception as e:                          # noqa: BLE001
        print(f"vault {method} failed: {e}")
        return None
    v = raw.get("value")
    if isinstance(v, dict) and "value" in v:        # GET wraps once
        v = v["value"]
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            pass
    return v if isinstance(v, dict) else None


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


def cmd_new(_args) -> int:
    acct = _new_account()
    stored = _vault("PUT", acct)
    print(f"created ak mailbox: {acct['address']}  (stored in vault: {bool(stored)})")
    return 0


def cmd_show(_args) -> int:
    acct = _vault("GET")
    if not acct:
        print("no ak mailbox in the vault -- run: python3 scripts/ak_mail.py new")
        return 1
    print(acct["address"])
    return 0


def cmd_inbox(_args) -> int:
    acct = _vault("GET")
    if not acct:
        print("no ak mailbox in the vault -- run: python3 scripts/ak_mail.py new")
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
    acct = _vault("GET")
    if not acct:
        print("no ak mailbox in the vault")
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
    sub.add_parser("new").set_defaults(fn=cmd_new)
    sub.add_parser("show").set_defaults(fn=cmd_show)
    sub.add_parser("inbox").set_defaults(fn=cmd_inbox)
    r = sub.add_parser("read")
    r.add_argument("id")
    r.set_defaults(fn=cmd_read)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
