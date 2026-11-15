#!/usr/bin/env python3
"""No workflow may queue on a self-hosted runner forever.

Measured 2026-11-15: PC1's self-hosted runner is dead (GitHub lists no runner;
Smart App Control blocks the unsigned `Runner.Listener.exe`; the tailnet funnel is
NXDOMAIN). A job on `[self-hosted, pc1]` with no such runner does not fail -- it
sits `queued` forever. The pod's own `account-watch` dispatch has been `queued`
since 2026-11-04 and cannot be cancelled (GitHub returns 409/403 -- it is a server
side zombie). So any `self-hosted` job MUST be gated by a `preflight` job that
fails fast when no runner is online.

This guard can FAIL: delete the `preflight` job (or its `needs:`) from
`pc1-task.yml` and it exits 1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "self-hosted" not in text:
            continue
        if re.search(r"^\s*preflight:\s*$", text, re.M) is None:
            offenders.append((path.name, "no `preflight:` job"))
            continue
        # The self-hosted job must depend on the preflight gate.
        if re.search(r"needs:\s*preflight", text) is None:
            offenders.append((path.name, "self-hosted job does not `needs: preflight`"))
        # The preflight itself must be able to fail.
        if re.search(r"exit\s+1", text) is None:
            offenders.append((path.name, "preflight cannot fail (no exit 1)"))

    if offenders:
        fail("workflows could queue on a dead self-hosted runner forever: "
             + "; ".join(f"{n} ({why})" for n, why in offenders))

    gated = [p.name for p in sorted(WORKFLOWS.glob("*.yml"))
             if "self-hosted" in p.read_text(encoding="utf-8")]
    print(f"OK: every self-hosted workflow is gated by a fail-fast preflight "
          f"({', '.join(gated) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
