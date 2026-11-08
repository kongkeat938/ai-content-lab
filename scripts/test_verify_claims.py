#!/usr/bin/env python3
"""Guard the verifier: it must be able to call a snapshot stale.

The whole point of verify_claims is to disagree with a committed number when the
live source has moved. A verifier that only ever says "match" would pass forever
and prove nothing, so this feeds it a snapshot whose numbers are deliberately old
and asserts it reports DIVERGED -- the exact case measured on 2026-11-08, when the
committed 28-day snapshot was 52-244% behind the live Analytics API because a viral
clip landed after the snapshot was taken.

No network here: the comparison is the part that must be right, and it takes the
snapshot as data.

    python3 scripts/test_verify_claims.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verify_claims as vc  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    # The real measured case: committed genx 5743 views / 24.2 h for the window
    # 2026-10-09..2026-11-06, live 19760 / 86.5 over the same window.
    snap = {
        "start": "2026-10-09", "end": "2026-11-06",
        "channels": {
            "genx": {"views": 5743, "watch_hours": 24.2},
            "dharma": {"views": 7018, "watch_hours": 39.4},
            "kongkeat": {"views": 3695, "watch_hours": 15.5},
        },
    }
    # Drive compare() with a fake network layer so the test stays offline and
    # still exercises the divergence decision.
    live = {
        "YT_CH1_REFRESH_TOKEN": [[19760, 5189]],
        "YT_CH2_REFRESH_TOKEN": [[10861, 3392]],
        "YT_CH4_REFRESH_TOKEN": [[5645, 1157]],
    }
    vc.access_token = lambda env: env
    vc.analytics = lambda token, start, end, metrics: live.get(token)

    r = vc.compare(snap)
    stale = [k for k, v in r.items() if v["status"] == "DIVERGED"]
    if set(stale) != {"genx", "dharma", "kongkeat"}:
        fail(f"the verifier did not flag the stale snapshot: {r}")

    # A snapshot that agrees within tolerance must NOT be flagged -- otherwise the
    # verifier is just noise.
    close = {
        "start": "2026-10-09", "end": "2026-11-06",
        "channels": {"genx": {"views": 19700, "watch_hours": 86.3},
                     "dharma": {"views": 10861, "watch_hours": 56.5},
                     "kongkeat": {"views": 5645, "watch_hours": 19.3}},
    }
    ok = [k for k, v in vc.compare(close).items() if v["status"] == "DIVERGED"]
    if ok:
        fail(f"a matching snapshot was wrongly flagged stale: {ok}")

    # An unreachable API must be reported, never silently treated as a match.
    def boom(env):
        raise RuntimeError("no network")
    vc.access_token = boom
    unreachable = vc.compare(snap)
    if any(v["status"] == "match" for v in unreachable.values()):
        fail("an unreachable source was reported as a match")

    print("OK: the verifier flags a stale snapshot, passes a fresh one, and never "
          "treats an unreachable source as agreement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
