#!/usr/bin/env python3
"""Fail if a GitHub workflow is malformed enough that GitHub rejects it.

Measured 2026-11-13: pausing the kongkeat channel (commit b39cdeb) commented out
the cron lines under `schedule:` but left the `schedule:` key in place. A block
whose only content is comments parses as `schedule: null`, and GitHub refuses the
WHOLE workflow: every run of ch4-longform.yml and publish-ch4.yml finished with
`failure` and **0 jobs** (nothing to even log). The pause was correct; the way it
was written silently killed both rails.

A guard that can FAIL: it sweeps every workflow file (never a hardcoded set) and
rejects a `schedule:` key whose block holds no list item (only comments/blank
lines before the next key). Commenting the whole key out (`# schedule:`) is fine
-- the key simply disappears.

It parses by hand on purpose: requirements.txt does not pin PyYAML, so importing
`yaml` would make this guard fail on a runner that lacks it.

    python3 scripts/test_workflow_yaml.py     # exit 0 = every workflow parses clean
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

SCHEDULE = re.compile(r"^(\s*)schedule\s*:\s*(#.*)?$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def check_schedule_block(name: str, text: str) -> list[str]:
    """Return a problem if any `schedule:` block has no list item."""
    problems: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = SCHEDULE.match(line)
        if not m:
            continue
        base = len(m.group(1))
        has_item = False
        for nxt in lines[i + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            # First real line after the key: it belongs to `schedule:` only if it
            # is indented deeper than the key (a `- cron:` list item).
            if _indent(nxt) > base and nxt.lstrip().startswith("-"):
                has_item = True
            break
        if not has_item:
            problems.append(
                f"{name}:{i + 1}: `schedule:` has no cron entry (a comment-only "
                "block parses as null and GitHub rejects the whole workflow) -- "
                "comment out the `schedule:` key itself instead"
            )
    return problems


def check_has_on(name: str, text: str) -> list[str]:
    if re.search(r"(?m)^on\s*:", text) or re.search(r"""(?m)^['"]on['"]\s*:""", text):
        return []
    return [f"{name}: no top-level `on:` trigger -- GitHub rejects the workflow"]


def main() -> int:
    files = sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml")))
    if not files:
        print("no workflow files found")
        return 1

    problems: list[str] = []
    for path in files:
        name = os.path.relpath(path, ROOT)
        text = open(path, encoding="utf-8").read()
        problems += check_has_on(name, text)
        problems += check_schedule_block(name, text)

    if problems:
        print("malformed workflow(s):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK: {len(files)} workflows parse clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
