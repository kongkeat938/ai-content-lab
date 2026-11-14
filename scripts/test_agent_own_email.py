#!/usr/bin/env python3
"""Every tool and every agent in the team must use its OWN mailbox, never K's.

K (2026-11-14): "ต่อไปเครื่องมือทุกอย่างใช้เมล์ตัวเองล็อกอินเลย รวมถึง agent ในทีมด้วย
ไม่ต้องใช้เมล์ K แล้ว". ak already owns a mailbox (`ak_mail.py`), but the workers in
`team.py` did not -- a worker that needed an email would have reached for K's.

This guard checks the wiring, not the network:
  * every team role has its OWN vault key, distinct from ak's and from each other;
  * `ak_mail.py` exposes a per-identity selector (`--as`) and a `roster` command;
  * `team.py` can mint/show a worker's mailbox and passes the worker its own identity;
  * no script signs up a TOOL with K's channel address.

It can FAIL: point two roles at the same vault key, drop `--as`, or make a worker
reuse K's email, and it exits 1. A guard that only checks the happy path proves nothing.

    python3 scripts/test_agent_own_email.py     # exit 0 = every identity has its own mail
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ak_mail  # noqa: E402
import team  # noqa: E402

# K's channel addresses -- the business assets. They must NEVER be a tool/agent signup.
K_ADDRESSES = ("kongkeat.938@gmail.com", "farmmer.938@gmail.com",
               "kongkeat.p3@gmail.com", "aerismusic8@gmail.com")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    # 1. Every identity resolves to its OWN vault key; none collides.
    keys: dict[str, str] = {}
    for identity in ["ak"] + list(team.TEAM):
        k = ak_mail._vault_key(identity)
        if not k:
            fail(f"identity {identity!r} has no vault key")
        if k in keys:
            fail(f"{identity!r} and {keys[k]!r} share vault key {k!r}; their mailboxes "
                 f"would collide (one would overwrite the other)")
        keys[k] = identity
    if ak_mail._vault_key("ak") == ak_mail._vault_key("researcher"):
        fail("a worker still shares ak's own vault key; it must have its own")

    # 2. The roster covers ak + every team role -- a new worker cannot be forgotten.
    roster = set(ak_mail.ROSTER)
    missing = set(team.TEAM) - roster
    if missing:
        fail(f"the mailbox roster omits team role(s) {sorted(missing)}; a new worker "
             f"would silently have no mailbox")
    if "ak" not in roster:
        fail("the mailbox roster does not include ak")

    # 3. The CLI exposes the per-identity selector and the roster command.
    src = open(os.path.join(HERE, "ak_mail.py"), encoding="utf-8").read()
    if "--as" not in src or "cmd_roster" not in src:
        fail("ak_mail.py has no `--as` selector or `roster` command; identities cannot "
             "be told apart")

    # 4. team.py can mint/show a worker's mailbox and labels each worker with its own.
    tsrc = open(os.path.join(HERE, "team.py"), encoding="utf-8").read()
    if "def mailbox(" not in tsrc:
        fail("team.py has no mailbox() helper; a worker has no way to learn its own address")
    if "cmd_mail" not in tsrc or '"mail"' not in tsrc:
        fail("team.py exposes no `mail` command; a worker's mailbox cannot be created")
    if "ห้ามใช้เมลของเจ้าของช่อง" not in tsrc:
        fail("team.dispatch does not tell the worker it must never use K's address")

    # 5. A store that fails MUST fail loudly. Measured 2026-11-14: `new` created an
    #    address at the provider but the vault write failed and it still exited 0 --
    #    the mailbox existed but was never recorded, so the next session read "no ak
    #    mailbox". Reintroducing that silent partial write must break this guard.
    real_vault = ak_mail._vault
    real_new = ak_mail._new_account
    ak_mail._new_account = lambda: {"address": "x@y.z", "password": "p"}
    ak_mail._vault = lambda *a, **k: None                 # the store fails
    try:
        rc = ak_mail.cmd_new(type("A", (), {"as_": "ak"})())
    finally:
        ak_mail._vault = real_vault
        ak_mail._new_account = real_new
    if rc == 0:
        fail("ak_mail.cmd_new exits 0 when the vault store fails; a created-but-unrecorded "
             "mailbox is lost and ak 'forgets' it again")

    # 6. No script may sign a TOOL up with K's channel address. A channel rail that
    #    authenticates as K's own account is fine (it is a business asset), so this
    #    only flags an address used as a signup/tool identity, matched conservatively.
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or name.startswith("test_"):
            continue
        if name in ("ak_mail.py",):                      # documents the rule itself
            continue
        text = open(os.path.join(HERE, name), encoding="utf-8").read()
        for addr in K_ADDRESSES:
            for i, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                if addr in line and any(w in low for w in ("signup", "sign up", "register",
                                                           "สมัคร", "tool_mail", "toolmail")):
                    fail(f"{name}:{i} signs a tool up with K's address {addr}: {line.strip()}")

    print(f"OK: {len(roster)} identities each have their own mailbox key; workers are told "
          f"to use their own and never K's")
    return 0


if __name__ == "__main__":
    sys.exit(main())
