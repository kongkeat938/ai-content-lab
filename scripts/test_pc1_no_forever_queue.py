#!/usr/bin/env python3
"""No workflow may queue on a self-hosted runner forever.

Measured 2026-11-15: PC1's self-hosted runner is dead (GitHub lists no runner;
Smart App Control blocks the unsigned `Runner.Listener.exe`; the tailnet funnel is
NXDOMAIN). A job on `[self-hosted, pc1]` with no such runner does not fail -- it
sits `queued` forever. The pod's own `account-watch` dispatch has been `queued`
since 2026-11-04 and cannot be cancelled (GitHub returns 409/403 -- it is a server
side zombie). So any `self-hosted` job MUST be gated by a `preflight` job that
fails fast when no runner is online.

This guard can FAIL: delete the `preflight` job (or its `needs:`, or the opt-in
default) from `pc1-task.yml` and it exits 1.
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


def strip_comments(text: str) -> str:
    """Drop YAML line comments so the scan looks at config, not prose."""
    return "\n".join(re.sub(r"(?<!:)#.*$", "", ln) for ln in text.splitlines())


def main() -> int:
    offenders = []
    gated = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "self-hosted" not in text:
            continue
        gated.append(path.name)
        src = strip_comments(text)
        if re.search(r"^\s*preflight:\s*$", text, re.M) is None:
            offenders.append((path.name, "no `preflight:` job"))
            continue
        if re.search(r"needs:\s*preflight", text) is None:
            offenders.append((path.name, "self-hosted job does not `needs: preflight`"))
        if re.search(r"exit\s+1", text) is None:
            offenders.append((path.name, "preflight cannot fail (no exit 1)"))
        # The gate must be an explicit opt-in that DEFAULTS OFF. A gate that probes
        # the runner list with the workflow token is not enough: that API 403s
        # ("Resource not accessible by integration") and any `|| echo 0` fallback
        # turns the 403 into a false pass (measured 2026-11-15).
        if not re.search(r"pc1_online:\s*\n(?:.*\n)*?\s*default:\s*false", text):
            offenders.append((path.name, "gate is not an opt-in defaulting to false"))
        if re.search(r"actions/runners", src):
            offenders.append((path.name, "gate probes actions/runners, which 403s "
                             "for the workflow token and can pass by mistake"))

    if offenders:
        fail("a self-hosted job could queue on a dead runner forever: "
             + "; ".join(f"{n} ({why})" for n, why in offenders))

    print(f"OK: every self-hosted workflow is gated by a fail-fast, opt-in preflight "
          f"({', '.join(gated) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
