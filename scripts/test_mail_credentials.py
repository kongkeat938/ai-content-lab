#!/usr/bin/env python3
"""Guard the mail credential: one secret, many accounts, and never a leak.

K will enter a mailbox password once and it must serve every account. Two things
must hold or the design is unsafe or useless:

  * one secret is enough -- IMAP_ACCOUNTS carries every account, so the password is
    typed a single time; the old IMAP_USER/IMAP_APP_PASSWORD pair still merges in
    without creating a duplicate account
  * the password never reaches the report -- the committed MAIL-ALERTS.md is in a
    public repository, so the check that reads the mail must not be able to print
    the credential even by accident

The IMAP server is faked (a real mailbox is not available here and must not be
required), but the code under test is the real inbox_alerts() path.

    python3 scripts/test_mail_credentials.py
"""
from __future__ import annotations

import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mail_watch as mw  # noqa: E402

PW = "abcd efgh ijkl mnop"  # Google shows app passwords with spaces; cosmetic
CLEAN = "abcdefghijklmnop"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


class FakeIMAP:
    """Enough of imaplib to run inbox_alerts() offline."""

    def __init__(self, *_a, **_k):
        pass

    def login(self, user, pw):
        self.user, self.pw = user, pw
        return ("OK", [b"logged in"])

    def select(self, _box):
        return ("OK", [b"1"])

    def search(self, _charset, _query):
        return ("OK", [b"1"])

    def fetch(self, _num, _spec):
        raw = (b"From: YouTube <noreply@youtube.com>\r\n"
               b"Subject: Your video was removed\r\n"
               b"Date: Wed, 08 Nov 2026 03:00:00 +0000\r\n\r\nbody\r\n")
        return ("OK", [(b"1 (RFC822 {10}", raw)])

    def logout(self):
        return ("BYE", [])


def main() -> int:
    # 1. One secret, several accounts, spaces stripped, duplicate merged away.
    os.environ["IMAP_ACCOUNTS"] = json.dumps([
        {"user": "kongkeat.938@gmail.com", "app_password": PW},
        {"user": "farmmer.938@gmail.com", "app_password": PW},
    ])
    os.environ["IMAP_USER"] = "kongkeat.938@gmail.com"  # same as above: no duplicate
    os.environ["IMAP_APP_PASSWORD"] = PW
    accounts = mw.mail_accounts()
    users = [u for _h, u, _p in accounts]
    if users != ["kongkeat.938@gmail.com", "farmmer.938@gmail.com"]:
        fail(f"one secret did not yield exactly the two accounts: {users}")
    if any(p != CLEAN for _h, _u, p in accounts):
        fail("the app password was not stripped of the cosmetic spaces")
    if any(h != "imap.gmail.com" for h, _u, _p in accounts):
        fail("the default host was not applied")

    # 2. The mapping form works too.
    os.environ["IMAP_ACCOUNTS"] = json.dumps({"a@gmail.com": PW})
    os.environ.pop("IMAP_USER", None)
    os.environ.pop("IMAP_APP_PASSWORD", None)
    if [u for _h, u, _p in mw.mail_accounts()] != ["a@gmail.com"]:
        fail("the mapping form of IMAP_ACCOUNTS was not accepted")

    # 3. No credential at all must read as BLIND, not as "all clear".
    os.environ.pop("IMAP_ACCOUNTS", None)
    alerts, status = mw.inbox_alerts(3)
    if alerts or "BLIND" not in status:
        fail(f"a missing credential did not read as BLIND: {status!r}")

    # 4. With a credential, the real path must flag the mail AND never print the
    #    password. This is the leak guard: the report is public.
    os.environ["IMAP_ACCOUNTS"] = json.dumps([{"user": "kongkeat.938@gmail.com",
                                               "app_password": PW}])
    mw.imaplib = types.SimpleNamespace(IMAP4_SSL=FakeIMAP)
    alerts, status = mw.inbox_alerts(3)
    if not alerts:
        fail("a removal mail was not flagged")
    blob = status + json.dumps(alerts, ensure_ascii=False)
    if CLEAN in blob or PW in blob:
        fail("the app password leaked into the alert output")
    if "kongkeat.938@gmail.com" not in status:
        fail("the account that was read is not named in the status")

    print("OK: one secret serves every account, duplicates merge, no credential "
          "reads as BLIND, and the password never reaches the report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
