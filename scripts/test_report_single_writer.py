#!/usr/bin/env python3
"""Guard that a generated report under docs/ has exactly ONE writer rail.

Measured 2026-11-13: `docs/CHANNEL-AUDIT-LATEST.md` was regenerated and committed
by TWO rails -- rogue-guard (every 30 min) and account-watch (daily). The file's
first line is a timestamp, so whenever the two overlapped the rebase conflicted on
that same line, the push was rejected, and the rogue-guard run -- the one that
hides a leaked-token clip -- died. A generated file whose header changes every run
must have a single writer; a second writer guarantees a conflict.

The sweep reads EVERY workflow and expands `for <var> in <paths>; do ... git add
...$var` loops, so a path committed through a loop variable is still counted (a
literal-only scan would have missed the very bug this guards). It never hardcodes
the set of files: it discovers them from the workflows.

    python3 scripts/test_report_single_writer.py     # exit 0 = one writer each
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows")

PATH_TOKEN = re.compile(r"^(docs|content)/[\w.\-]+$")
FOR_LOOP = re.compile(r"^\s*for\s+\w+\s+in\s+(.+?);\s*do\b")


def tokens(line: str) -> list[str]:
    out = []
    for raw in line.split():
        t = raw.strip('"\'' + "{}")
        if PATH_TOKEN.match(t):
            out.append(t)
    return out


def committed_paths(text: str) -> set[str]:
    """Every docs/content path this workflow commits (literal or via a for loop)."""
    found: set[str] = set()
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if "git add" in line:
            found.update(tokens(line))
        m = FOR_LOOP.match(line)
        if m:
            found.update(tokens(m.group(1)))
    return found


def main() -> int:
    writers: dict[str, set[str]] = {}
    for name in sorted(os.listdir(WF)):
        if not name.endswith((".yml", ".yaml")):
            continue
        text = open(os.path.join(WF, name), encoding="utf-8").read()
        for path in committed_paths(text):
            writers.setdefault(path, set()).add(name)

    # Only docs/ reports are generated-with-a-volatile-header and must be
    # single-writer. content/ ledgers are append-only and union-merged on purpose,
    # so several rails writing them is correct.
    clash = {p: w for p, w in writers.items()
             if p.startswith("docs/") and len(w) > 1}
    if clash:
        for p, w in sorted(clash.items()):
            print(f"FAIL: {p} is committed by {len(w)} rails: {sorted(w)} -- "
                  "a generated report needs ONE writer (a second guarantees a "
                  "rebase conflict on its timestamp header)", file=sys.stderr)
        return 1

    print(f"OK: every docs/ report has a single writer "
          f"({sum(1 for p in writers if p.startswith('docs/'))} checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
