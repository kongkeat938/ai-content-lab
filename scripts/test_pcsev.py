#!/usr/bin/env python3
"""Guard the PCSEV principle itself, so it cannot be dropped again.

K (2026-11-09): "แสดงว่า หลักการ pcsev ไม่ได้ถูกเก็บไว้" -- the principle WAS kept,
but only in a daily log / the archive, NOT in the MEMORY.md index the loader injects
every session. So it silently stopped shaping the work: a fix was shown as an answer
instead of a Problem->Cause->Solution->Execute->Verify chain with a live Verify.

A principle that lives only in a deep file is not kept. This test fails if PCSEV
disappears from the index, from AGENTS.md, or from its own doc -- so a later edit
cannot quietly drop it again.

    python3 scripts/test_pcsev.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MEMORY = os.path.join(ROOT, ".openhands", "memory", "MEMORY.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")
DOC = os.path.join(ROOT, "docs", "PCSEV-VERIFY-2026-11-08.md")

STEPS = ["Problem", "Cause", "Solution", "Execute", "Verify"]

FAILS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(name)


def main() -> int:
    check("PCSEV doc exists", os.path.exists(DOC), DOC)
    check("AGENTS.md exists", os.path.exists(AGENTS), AGENTS)

    mem = open(MEMORY, encoding="utf-8").read() if os.path.exists(MEMORY) else ""
    check("MEMORY.md index names PCSEV", "PCSEV" in mem)
    check("MEMORY.md carries the live-Verify rule",
          "live API" in mem and "counter with an invariant" in mem)

    ag = open(AGENTS, encoding="utf-8").read() if os.path.exists(AGENTS) else ""
    check("AGENTS.md names PCSEV", "PCSEV" in ag)
    for step in STEPS:
        check(f"AGENTS.md states step '{step}'", step in ag)
    check("AGENTS.md states the Verify trust order",
          "live API" in ag and "a test that can FAIL" in ag)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: the PCSEV principle is kept where every session reads it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
