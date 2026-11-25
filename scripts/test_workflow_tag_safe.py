#!/usr/bin/env python3
"""A tag push must never run a rail.

Measured 2026-11-25: creating a GitHub release creates a tag, and a tag push
fires every `push:` workflow that has no `branches:`/`tags:` filter -- GitHub
does not evaluate `paths:` for tag pushes. Two releases therefore ran
publish-shorts three times each (the cadence guard blocked the uploads, logs:
"only 0.7h since the last post (need 2.0h)").

This guard fails if any workflow can be started by a tag push.
"""
from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUSH = re.compile(r"^  push:\n((?:    .*\n)+)", re.M)


def unsafe(text: str) -> bool:
    m = PUSH.search(text)
    if not m:
        return False
    body = m.group(1)
    return "branches" not in body and "tags" not in body


def main() -> int:
    # The guard must be able to fail: a synthetic workflow with the old shape.
    assert unsafe("on:\n  push:\n    paths:\n      - 'a'\n"), "guard cannot detect the bug it exists for"
    assert not unsafe("on:\n  push:\n    branches: [main]\n    paths:\n      - 'a'\n")

    bad = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(ROOT, ".github/workflows/*.yml")))
           if unsafe(open(p, encoding="utf-8").read())]
    if bad:
        print(f"FAIL: {len(bad)} workflow(s) can be started by a tag push: {', '.join(bad)}")
        return 1
    print("ok   every push-triggered workflow is limited to a branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
