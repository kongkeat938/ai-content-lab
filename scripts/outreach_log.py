#!/usr/bin/env python3
"""The outreach ledger: who was contacted, when, and what money actually arrived.

Two jobs, both deterministic:
  * stop the same channel being contacted twice inside the cooldown -- including
    after a decline (a "no" is not an invitation to try again next week),
  * keep orders and money apart: creating an order is not revenue. Money counts
    only once it is recorded as received, and a refund takes it back out.

    python3 scripts/outreach_log.py add UC... --name "channel"
    python3 scripts/outreach_log.py log UC... --status contacted --note "..."
    python3 scripts/outreach_log.py due
    python3 scripts/outreach_log.py check UC...
    python3 scripts/outreach_log.py order UC... --package B --amount 890
    python3 scripts/outreach_log.py pay o1          # money received
    python3 scripts/outreach_log.py deliver o1
    python3 scripts/outreach_log.py approve o1
    python3 scripts/outreach_log.py refund o1
    python3 scripts/outreach_log.py report

A contact inside COOLDOWN_DAYS is refused for every status, declined included.
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
CLOSED = ("won", "lost", "declined")          # never offered as "due"
ORDER_STATES = ("created", "paid", "delivered", "approved", "refunded")
REVENUE_STATES = ("paid", "delivered", "approved")
CMD_STATE = {"pay": "paid", "deliver": "delivered", "approve": "approved", "refund": "refunded"}
TRANSITIONS = {
    "paid": ("created",),
    "delivered": ("paid",),
    "approved": ("delivered",),
    "refunded": ("paid", "delivered", "approved"),
}


def load() -> dict:
    if os.path.exists(STORE):
        return json.load(open(STORE, encoding="utf-8"))
    return {"channels": {}, "orders": []}


def save(d: dict) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    json.dump(d, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    return (time.time() - time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))) / 86400


def blocked(entry: dict) -> bool:
    """Every status is inside the cooldown, a decline included."""
    d = days_since(entry.get("last_contacted_at"))
    return d is not None and d < COOLDOWN_DAYS


def find_order(d: dict, oid: str) -> dict | None:
    return next((o for o in d["orders"] if o["id"] == oid), None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("add", "log", "due", "check", "order", "orders",
                                    "pay", "deliver", "approve", "refund", "report"))
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
                  f"(cooldown {COOLDOWN_DAYS}, status {e['status']}) -- do not contact again")
            return 1
        e["status"] = a.status or e["status"]
        if a.status == "contacted":
            e["last_contacted_at"] = now()
        if a.note:
            e.setdefault("notes", []).append({"at": now(), "text": a.note})
        save(d)
        print(f"ok   {a.cid} -> {e['status']}")
        return 0

    if a.cmd == "check":
        e = ch.get(a.cid)
        if not e:
            print("ok   never contacted")
            return 0
        if blocked(e):
            print(f"BLOCKED: {days_since(e['last_contacted_at']):.1f} days since last contact "
                  f"(status {e['status']})")
            return 1
        print(f"ok   contact allowed (status {e['status']})")
        return 0

    if a.cmd == "due":
        rows = [(cid, e) for cid, e in ch.items() if not blocked(e) and e["status"] not in CLOSED]
        for cid, e in rows:
            print(f"  {e['status']:9} {cid}  {e.get('name', '')}")
        print(f"{len(rows)} channel(s) contactable now")
        return 0

    if a.cmd == "order":
        oid = f"o{len(d['orders']) + 1}"
        d["orders"].append({"id": oid, "cid": a.cid, "package": a.package, "amount": a.amount,
                            "status": "created", "created_at": now(), "paid_at": None})
        save(d)
        print(f"ok   {oid} created ({a.package} {a.amount:.0f} THB) -- NOT revenue until paid")
        return 0

    if a.cmd == "orders":
        for o in d["orders"]:
            print(f"  {o['id']:4} {o['status']:9} {o['amount']:>8.0f} THB  {o['package']:3} {o['cid']}")
        print(f"{len(d['orders'])} order(s)")
        return 0

    if a.cmd in CMD_STATE:
        state = CMD_STATE[a.cmd]
        o = find_order(d, a.cid or "")
        if not o:
            print(f"no order {a.cid}")
            return 1
        if o["status"] not in TRANSITIONS[state]:
            print(f"REFUSED: {o['id']} is {o['status']}, cannot become {state}")
            return 1
        o["status"] = state
        o[f"{state}_at"] = now()
        if state == "paid":
            o["paid_at"] = now()
        save(d)
        print(f"ok   {o['id']} -> {state}")
        return 0

    # report
    orders = d["orders"]
    def total(states):
        return sum(o["amount"] for o in orders if o["status"] in states)
    received = total(REVENUE_STATES)          # a refunded order leaves this set
    refunded = sum(o["amount"] for o in orders if o.get("refunded_at"))
    pending = total(("created",))
    counts = {}
    for e in ch.values():
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    contacted = sum(v for k, v in counts.items() if k in ("contacted", "replied", "sample", "won", "lost"))
    print(f"channels in ledger : {len(ch)}  {counts}")
    print(f"contacted          : {contacted}")
    print(f"orders created     : {len(orders)}  ({pending:.0f} THB not yet paid)")
    print(f"money received     : {received:.0f} THB   (paid/delivered/approved; refunds already removed)")
    print(f"refunded           : {refunded:.0f} THB")
    print(f"costs (recorded)   : 0 THB   (free tooling only; no cash spent)")
    print(f"conversion         : {(len(orders)/contacted*100 if contacted else 0):.1f}% of contacted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
