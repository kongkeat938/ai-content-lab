#!/usr/bin/env python3
"""The revoke tool must not fire without --confirm, and must never claim a false stop.

Revoking a grant also stops our own rails for that channel until the owner
re-consents, so the safe default matters. This locks the gate, and proves the
guard can FAIL: the dry run must NOT print a revoke line.

    python3 scripts/test_revoke_token.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import revoke_token as rt  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("the tool knows the three active channels")
    check("genx/dharma/kongkeat-story are mapped",
          set(rt.CHANNELS) == {"genx", "dharma", "kongkeat-story"}, str(sorted(rt.CHANNELS)))

    print("without --confirm it is a dry run and fires nothing")
    env = {k: v for k, v in os.environ.items() if not k.startswith("YT_")}
    env["YT_CH1_REFRESH_TOKEN"] = "fake-token-for-the-guard"
    r = subprocess.run([sys.executable, os.path.join(HERE, "revoke_token.py"),
                        "--channel", "genx"], capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    check("exit 0 on the dry run", r.returncode == 0, f"rc={r.returncode}")
    check("it says DRY RUN", "DRY RUN" in out)
    check("it did NOT revoke (the gate can fail)", "revoke ->" not in out, out[-200:])
    check("it never prints the token value", "fake-token-for-the-guard" not in out)

    print("it will not claim a stop it cannot measure")
    # With no client credentials it cannot test the grant, so it must assume alive
    # rather than report a false "already dead".
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET"):
        os.environ.pop(k, None)
    check("still_alive() is True when it cannot test", rt.still_alive("genx", "x") is True)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: revoke needs --confirm and never reports an unmeasured stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
