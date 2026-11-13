#!/usr/bin/env python3
"""ak's worker team must be wired to real advisors, and a bad name must fail loudly.

K (2026-11-13): "สร้างทีมงานของตัวเองใหม่ เอาแบบที่คัดแล้วช่วยงานได้จริง ๆ" and "เอามา
ช่วยทำงาน ไม่ต้องเอามาปรึกษาอย่างเดียว". The team (`team.py`) is only useful if every worker
points at an advisor that actually exists in `advise.py` -- a missing name is the exact
`.get()+continue` bug that once silently emptied the light panel for days.

This guard can FAIL: point a worker at an unknown advisor, empty the roster, or drop a role's
brief, and it exits 1. It also asserts `dispatch` refuses an unknown role instead of returning
an empty string.

    python3 scripts/test_team.py     # exit 0 = the team is wired and self-guarding
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import advise  # noqa: E402
import team  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    if len(team.TEAM) < 3:
        fail(f"the team has only {len(team.TEAM)} worker(s); a team needs several roles")

    for role, spec in team.TEAM.items():
        if spec.get("advisor") not in advise.ADVISORS:
            fail(f"worker {role!r} points at unknown advisor {spec.get('advisor')!r} "
                 f"(known: {sorted(advise.ADVISORS)})")
        if not spec.get("prompt") or len(spec["prompt"]) < 30:
            fail(f"worker {role!r} has no real brief")

    # every role named as a default in the CLI must resolve through worker()
    for role in team.TEAM:
        try:
            team.worker(role)
        except KeyError as exc:
            fail(f"worker({role!r}) raised: {exc}")

    # the loud-fail property: an unknown role must raise, never return ""
    try:
        team.dispatch("no-such-role", "x")
        fail("dispatch() accepted an unknown role instead of raising")
    except KeyError:
        pass

    print(f"OK: {len(team.TEAM)} workers, all bound to real advisors; bad roles fail loudly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
