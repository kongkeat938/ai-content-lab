#!/usr/bin/env python3
"""Fail if a GitHub workflow is malformed enough that GitHub rejects it.

Measured 2026-11-13: pausing the kongkeat channel (commit b39cdeb) commented out
the cron lines under `schedule:` but left the `schedule:` key in place. A block
whose only content is comments parses as `schedule: null`, and GitHub refuses the
WHOLE workflow: every run of ch4-longform.yml and publish-ch4.yml finished with
`failure` and **0 jobs** (nothing to even log). The pause was correct; the way it
was written silently killed both rails.

A guard that can FAIL: it sweeps every workflow file (never a hardcoded set) and
rejects a null-valued `schedule` (and a null `on`/`jobs`). A null `workflow_dispatch`
or `push` is fine -- that is the normal spelling for "no inputs / no filters" -- so
the guard deliberately does NOT flag those. Commenting the whole key out
(`# schedule:`) is fine too; the key simply disappears.

    python3 scripts/test_workflow_yaml.py     # exit 0 = every workflow parses clean
"""
from __future__ import annotations

import glob
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")


def main() -> int:
    files = sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml")))
    if not files:
        print("no workflow files found")
        return 1

    problems: list[str] = []
    for path in files:
        name = os.path.relpath(path, ROOT)
        try:
            doc = yaml.safe_load(open(path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report any parse error
            problems.append(f"{name}: YAML will not parse: {exc}")
            continue
        if not isinstance(doc, dict):
            problems.append(f"{name}: top level is not a mapping")
            continue

        # PyYAML turns the bare key `on` into the boolean True.
        on = doc.get(True, doc.get("on"))
        if on is None:
            problems.append(f"{name}: no `on:` trigger -- GitHub rejects the workflow")
        elif isinstance(on, dict):
            # Only `schedule` is a hard error when null: a comment-only block there
            # yields `schedule: null` and GitHub rejects the whole file (measured
            # 2026-11-13). `workflow_dispatch: null` / `push: null` are the normal
            # spelling for "no inputs / no filters" and must NOT be flagged.
            if "schedule" in on and on["schedule"] is None:
                problems.append(
                    f"{name}: `on.schedule:` is null (a comment-only block) -- "
                    "GitHub rejects the whole workflow; comment out the key "
                    "itself instead"
                )

        for key in ("jobs",):
            if key in doc and doc[key] is None:
                problems.append(f"{name}: `{key}:` is null")

    if problems:
        print("malformed workflow(s):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"OK: {len(files)} workflows parse clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
