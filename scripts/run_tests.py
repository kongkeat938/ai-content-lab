#!/usr/bin/env python3
"""Run every scripts/test_*.py and report a single verdict.

Why this exists: the repo had no CI, so "the tests pass" was a claim made in
chat and nothing re-checked it. GitHub Actions now runs this on every push and
pull request.

    python3 scripts/run_tests.py            # all tests
    python3 scripts/run_tests.py --list     # names only
    CI=1 python3 scripts/run_tests.py       # skips tests that need live secrets

A test that needs a YouTube token cannot pass in CI (no secrets are given to a
workflow that runs on every push), so those are skipped there and still run in
the pod. The list is measured, not guessed: run the suite with the secrets
unset and see which fail.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Measured 2026-11-25 by running the suite with every YT_*/GITHUB_TOKEN unset.
NEEDS_SECRETS: set[str] = set()


def main() -> int:
    tests = sorted(glob.glob(os.path.join(ROOT, "scripts", "test_*.py")))
    if "--list" in sys.argv:
        print("\n".join(os.path.basename(t) for t in tests))
        return 0
    ci = bool(os.environ.get("CI"))
    passed, failed, skipped = [], [], []
    t0 = time.time()
    for t in tests:
        name = os.path.basename(t)
        if ci and name in NEEDS_SECRETS:
            skipped.append(name)
            print(f"SKIP {name} (needs live secrets)")
            continue
        r = subprocess.run([sys.executable, t], capture_output=True, text=True,
                           timeout=900, stdin=subprocess.DEVNULL)
        if r.returncode == 0:
            passed.append(name)
            print(f"PASS {name}")
        else:
            failed.append(name)
            tail = " ".join((r.stdout + r.stderr).strip().splitlines()[-3:])[:300]
            print(f"FAIL {name} :: {tail}")
    print(f"\n{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped "
          f"in {time.time() - t0:.0f}s")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
