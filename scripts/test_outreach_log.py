#!/usr/bin/env python3
"""Guards for the outreach ledger.

The two bugs this test exists for (found in review, 2026-11-25):
  1. a declined customer was treated as CLOSED, so the cooldown let us contact
     them again the next day -- the exact behaviour that reads as spam;
  2. `order` counted the money at creation, so an unpaid order showed up as
     revenue.

Both are driven here as failing paths, and the cooldown is also aged past 14
days to prove it expires instead of blocking forever.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "outreach_log.py")
fails = 0


def check(ok: bool, label: str) -> None:
    global fails
    print(("  ok   " if ok else "  FAIL ") + label)
    if not ok:
        fails += 1


def run(store: str, *args: str) -> tuple[int, str]:
    env = dict(os.environ, OUTREACH_STORE=store)
    r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store = os.path.join(tmp, "outreach.json")
        check(run(store, "check", "UC1")[0] == 0, "a fresh channel is contactable")
        check(run(store, "log", "UC1", "--status", "contacted")[0] == 0, "first contact recorded")
        code, out = run(store, "log", "UC1", "--status", "contacted")
        check(code == 1 and "REFUSED" in out, "second contact inside the cooldown is REFUSED")

        check(run(store, "log", "UC1", "--status", "declined")[0] == 0, "a decline can be recorded")
        code, out = run(store, "log", "UC1", "--status", "contacted")
        check(code == 1 and "REFUSED" in out, "REGRESSION: a declined channel is still refused inside 14 days")
        code, out = run(store, "check", "UC1")
        check(code == 1 and "BLOCKED" in out, "check() blocks a declined channel too")

        d = json.load(open(store, encoding="utf-8"))
        d["channels"]["UC1"]["last_contacted_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 15 * 86400))
        json.dump(d, open(store, "w", encoding="utf-8"))
        check(run(store, "check", "UC1")[0] == 0, "the cooldown expires after 14 days")

        check(run(store, "order", "UC1", "--package", "B", "--amount", "890")[0] == 0, "an order can be created")
        code, out = run(store, "report")
        check("money received     : 0 THB" in out, "REGRESSION: a created order is NOT revenue")
        check("890 THB not yet paid" in out, "the unpaid amount is shown as pending")

        code, out = run(store, "deliver", "o1")
        check(code == 1 and "REFUSED" in out, "delivery before payment is REFUSED")
        check(run(store, "pay", "o1")[0] == 0, "payment can be recorded")
        check("money received     : 890 THB" in run(store, "report")[1], "paid money counts as received")
        code, out = run(store, "pay", "o1")
        check(code == 1 and "REFUSED" in out, "paying twice is REFUSED")
        check(run(store, "deliver", "o1")[0] == 0, "delivery after payment is allowed")
        check(run(store, "refund", "o1")[0] == 0, "a refund can be recorded")
        code, out = run(store, "report")
        check("money received     : 0 THB" in out, "a refund takes the money back out")
        check("refunded           : 890 THB" in out, "the refund is reported separately")
    print("FAIL" if fails else "PASS", "test_outreach_log")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
