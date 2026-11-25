#!/usr/bin/env python3
"""The outreach ledger: who was contacted, when, and what came back.

Two jobs, both cheap and deterministic:
  * stop the same channel being contacted twice inside the cooldown (the thing
    that turns an offer into spam),
  * hold the money facts so a revenue number is read from a record, never from
    memory.

    python3 scripts/outreach_log.py add UC... --name "ช่อง"
    python3 scripts/outreach_log.py log UC... --status contacted --note "..."
    python3 scripts/outreach_log.py due
    python3 scripts/outreach_log.py order UC... --package B --amount 890
    python3 scripts/outreach_log.py report

Statuses: new, contacted, replied, sample, won, lost, declined.
A channel contacted inside COOLDOWN_DAYS is refused (`check` exits 1).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.environ.get("OUTREACH_STORE") or os.path.join(ROOT, "content", "outreach.json")
COOLDOWN_DAYS = 14
STATUSES = ("new", "contacted", "replied", "sample", "won", "lost", "declined")
CLOSED = ("won", "lost", "declined")


def load() -> dict:
    if os.path.exists(STORE):
        return json.load(open(STORE, encoding="utf-8"))
    return {"channels": {}, "orders": []}


def save(d: dict) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    json.dump(d, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    return (time.time() - time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))) / 86400


def blocked(entry: dict) -> bool:
    d = days_since(entry.get("last_contacted_at"))
    return entry.get("status") not in CLOSED and d is not None and d < COOLDOWN_DAYS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("add", "log", "due", "check", "order", "report"))
    ap.add_argument("cid", nargs="?")
    ap.add_argument("--name", default="")
    ap.add_argument("--status", choices=STATUSES)
    ap.add_argument("--note", default="")
    ap.add_argument("--package", default="")
    ap.add_argument("--amount", type=float, default=0.0)
    a = ap.parse_args()
    d = load()
    ch = d["channels"]

    if a.cmd == "add":
        e = ch.setdefault(a.cid, {"name": a.name, "status": "new", "last_contacted_at": None, "notes": []})
        e["name"] = a.name or e.get("name", "")
        save(d)
        print(f"ok   {a.cid} in the ledger")
        return 0

    if a.cmd == "log":
        e = ch.setdefault(a.cid, {"name": "", "status": "new", "last_contacted_at": None, "notes": []})
        if a.status == "contacted" and blocked(e):
            print(f"REFUSED: contacted {days_since(e['last_contacted_at']):.1f} days ago "
                  f"(cooldown {COOLDOWN_DAYS}) -- do not contact again")
            return 1
        e["status"] = a.status or e["status"]
        if a.status == "contacted":
            e["last_contacted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if a.note:
            e.setdefault("notes", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "text": a.note})
        save(d)
        print(f"ok   {a.cid} -> {e['status']}")
        return 0

    if a.cmd == "check":
        e = ch.get(a.cid)
        if not e:
            print("ok   never contacted")
            return 0
        if blocked(e):
            print(f"BLOCKED: {days_since(e['last_contacted_at']):.1f} days since last contact")
            return 1
        print(f"ok   contact allowed (status {e['status']})")
        return 0

    if a.cmd == "due":
        rows = [(cid, e) for cid, e in ch.items() if not blocked(e) and e["status"] not in CLOSED]
        for cid, e in rows:
            print(f"  {e['status']:9} {cid}  {e.get('name','')}")
        print(f"{len(rows)} channel(s) contactable now")
        return 0

    if a.cmd == "order":
        d["orders"].append({"cid": a.cid, "package": a.package, "amount": a.amount,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        if a.cid in ch:
            ch[a.cid]["status"] = "won"
        save(d)
        print(f"ok   order recorded: {a.package} {a.amount:.0f} THB")
        return 0

    # report
    orders = d["orders"]
    rev = sum(o["amount"] for o in orders)
    counts = {}
    for e in ch.values():
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    contacted = sum(v for k, v in counts.items() if k in ("contacted", "replied", "sample", "won", "lost"))
    print(f"channels in ledger : {len(ch)}  {counts}")
    print(f"contacted          : {contacted}")
    print(f"orders             : {len(orders)}")
    print(f"revenue (recorded) : {rev:.0f} THB")
    print(f"costs (recorded)   : 0 THB   (no cash spent: free tooling only)")
    print(f"conversion         : {(len(orders)/contacted*100 if contacted else 0):.1f}% of contacted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
