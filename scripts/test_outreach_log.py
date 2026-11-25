#!/usr/bin/env python3
"""The ledger must refuse a second contact inside the cooldown.

A guard that only checks the happy path proves nothing, so this test drives the
refusal path too: log a contact, then try again and expect exit 1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

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
        check(run(store, "add", "UC1", "--name", "ช่องทดสอบ")[0] == 0, "add writes the entry")
        check(run(store, "log", "UC1", "--status", "contacted")[0] == 0, "first contact is recorded")
        code, out = run(store, "check", "UC1")
        check(code == 1 and "BLOCKED" in out, "a second contact inside the cooldown is BLOCKED")
        code, out = run(store, "log", "UC1", "--status", "contacted")
        check(code == 1 and "REFUSED" in out, "logging a second contact is REFUSED")
        check(run(store, "due")[1].strip().endswith("0 channel(s) contactable now"), "the blocked channel is not in 'due'")
        check(run(store, "log", "UC1", "--status", "declined")[0] == 0, "a reply can move the status")
        check(run(store, "due")[1].strip().endswith("0 channel(s) contactable now"), "a declined channel is not in 'due'")
        check(run(store, "order", "UC1", "--package", "B", "--amount", "890")[0] == 0, "an order is recorded")
        code, out = run(store, "report")
        check(code == 0 and "890" in out, "the report counts the money")
        d = json.load(open(store, encoding="utf-8"))
        check(d["channels"]["UC1"]["status"] == "won", "an order flips the channel to won")
        check(len(d["orders"]) == 1, "exactly one order")
    print("FAIL" if fails else "PASS", "test_outreach_log")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
