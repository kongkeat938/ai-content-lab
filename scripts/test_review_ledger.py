#!/usr/bin/env python3
"""Prove the Gemini review ledger can FAIL (K, 2026-11-19).

K's rule: nothing enters main without a recorded Gemini APPROVE. A ledger that
only ever prints "ok" is the false pass this repo keeps getting bitten by -- a
gate probing something it cannot read, then reporting success. So every check
below is exercised in BOTH directions against a throwaway tree: the failure it
exists to catch must actually fail, and the healthy case must pass.

The one that matters most: an *edited baseline* file. Baseline means "predates
the rule", not "exempt". If editing a baseline file left it exempt, then any
file could be quietly moved into the safe set by touching it, and the rule would
cover nothing.

    python3 scripts/test_review_ledger.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import review_ledger as R  # noqa: E402

FAILS = []


def check(name: str, ok: bool, got: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + name + (f" -- {got}" if got else ""))
    if not ok:
        FAILS.append(name)


def build(root: str, files: dict[str, str]) -> None:
    for name, body in files.items():
        p = os.path.join(root, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)


def digest(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def ledger_for(root: str, approved=(), baseline=(), evidence_text="APPROVE") -> dict:
    os.makedirs(os.path.join(root, "docs", "reviews"), exist_ok=True)
    ev = os.path.join(root, "docs", "reviews", "ev.txt")
    with open(ev, "w", encoding="utf-8") as fh:
        fh.write(evidence_text)
    return {
        "approved": {n: {"sha256": digest(os.path.join(root, n)), "verdict": "APPROVE",
                         "evidence": "docs/reviews/ev.txt"} for n in approved},
        "baseline": {n: {"sha256": digest(os.path.join(root, n))} for n in baseline},
    }


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="review-ledger-")
    try:
        build(tmp, {"scripts/a.py": "print('a')\n",
                    "scripts/b.py": "print('b')\n",
                    ".github/workflows/w.yml": "name: w\n"})

        # 1. A file in neither set is invisible. This is the false pass.
        led = ledger_for(tmp, approved=["scripts/a.py"], baseline=[".github/workflows/w.yml"])
        problems, _ = R.check(led, root=tmp)
        check("a file with no entry fails",
              any("scripts/b.py" in p and "no review entry" in p for p in problems),
              "; ".join(problems)[:120])

        # 2. The healthy case must pass, or the guard is a permanent red light.
        led = ledger_for(tmp, approved=["scripts/a.py", "scripts/b.py"],
                         baseline=[".github/workflows/w.yml"])
        problems, stats = R.check(led, root=tmp)
        check("every file accounted for passes", not problems, "; ".join(problems)[:120])
        check("stats count approved separately from baseline",
              stats == {"reviewable": 3, "approved": 2, "baseline": 1}, str(stats))

        # 3. Editing an approved file must go stale.
        with open(os.path.join(tmp, "scripts/a.py"), "a", encoding="utf-8") as fh:
            fh.write("# edit\n")
        problems, _ = R.check(led, root=tmp)
        check("editing an approved file fails (stale)",
              any("scripts/a.py" in p and "changed since it was reviewed" in p for p in problems),
              "; ".join(problems)[:120])

        # 4. Editing a BASELINE file must stop being exempt. This is the one that
        #    decides whether the rule covers anything at all.
        build(tmp, {"scripts/a.py": "print('a')\n"})
        with open(os.path.join(tmp, ".github/workflows/w.yml"), "a", encoding="utf-8") as fh:
            fh.write("# edit\n")
        problems, _ = R.check(led, root=tmp)
        check("editing a baseline file fails (no longer predates the rule)",
              any("w.yml" in p and "no longer the file that predated" in p for p in problems),
              "; ".join(problems)[:120])

        # 5. A verdict that is not APPROVE must not pass. 'APPROVE WITH CHANGES'
        #    is a real Gemini answer -- it is not permission to ship.
        build(tmp, {".github/workflows/w.yml": "name: w\n"})
        led = ledger_for(tmp, approved=["scripts/a.py", "scripts/b.py"],
                         baseline=[".github/workflows/w.yml"],
                         evidence_text="APPROVE WITH CHANGES: rename this function")
        problems, _ = R.check(led, root=tmp)
        check("'APPROVE WITH CHANGES' is not a pass",
              any("not APPROVE" in p for p in problems), "; ".join(problems)[:120])

        # 6. A REJECT must fail.
        led = ledger_for(tmp, approved=["scripts/a.py", "scripts/b.py"],
                         baseline=[".github/workflows/w.yml"], evidence_text="REJECT: unsafe")
        problems, _ = R.check(led, root=tmp)
        check("REJECT fails", any("'REJECT'" in p for p in problems), "; ".join(problems)[:120])

        # 7. A missing evidence file must read as unknown, never as a pass.
        led = ledger_for(tmp, approved=["scripts/a.py", "scripts/b.py"],
                         baseline=[".github/workflows/w.yml"])
        os.unlink(os.path.join(tmp, "docs", "reviews", "ev.txt"))
        problems, _ = R.check(led, root=tmp)
        check("missing evidence fails (unknown is not a pass)",
              any("missing or has no verdict" in p for p in problems), "; ".join(problems)[:120])

        # 8. A ledger entry for a file that is gone must fail, or a deleted
        #    reviewed file keeps a phantom approval alive forever.
        build(tmp, {"docs/reviews/ev.txt": "APPROVE"})
        led = ledger_for(tmp, approved=["scripts/a.py", "scripts/b.py"],
                         baseline=[".github/workflows/w.yml"])
        led["approved"]["scripts/gone.py"] = {"sha256": "0" * 64, "verdict": "APPROVE",
                                              "evidence": "docs/reviews/ev.txt"}
        problems, _ = R.check(led, root=tmp)
        check("an entry for a missing file fails",
              any("scripts/gone.py" in p and "no longer on disk" in p for p in problems),
              "; ".join(problems)[:120])

        # 9. The sweep must come from disk, not a hardcoded list: a brand-new file
        #    of a kind the guard covers must be seen without editing the guard.
        build(tmp, {"scripts/brand_new.py": "x = 1\n"})
        led = ledger_for(tmp, approved=["scripts/a.py", "scripts/b.py"],
                         baseline=[".github/workflows/w.yml"])
        problems, stats = R.check(led, root=tmp)
        check("a brand-new file is swept from disk",
              stats["reviewable"] == 4 and any("brand_new.py" in p for p in problems),
              str(stats))

        # 10. The real repo must be clean right now, or the rule is already broken.
        problems, stats = R.check(root=R.ROOT)
        check("the live repo has no review problems", not problems,
              "; ".join(problems)[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: the review ledger fails on every path it is meant to catch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
