#!/usr/bin/env python3
"""A tag push must never run a rail.

Measured 2026-11-25: creating a GitHub release creates a tag, and a tag push
fires every `push:` workflow with no `branches:`/`tags:` filter -- GitHub does
not evaluate `paths:` for tag pushes. Two releases therefore ran publish-shorts
three times each (the cadence guard blocked the uploads: "only 0.7h since the
last post").

The check parses the YAML instead of matching text, so it also catches the flow
form (`on: {push: {paths: [...]}}`) and `on: push` with no filter at all.
"""
from __future__ import annotations

import glob
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def push_trigger(doc) -> object:
    if not isinstance(doc, dict):
        return None
    # PyYAML reads the bare key `on` as boolean True (YAML 1.1).
    for key in ("on", True):
        if key in doc:
            return doc[key]
    return None


def unsafe(text: str) -> bool:
    doc = yaml.safe_load(text)
    trig = push_trigger(doc)
    if trig is None:
        return False
    if isinstance(trig, str):
        return trig == "push"
    if isinstance(trig, list):
        return "push" in trig
    if isinstance(trig, dict) and "push" in trig:
        spec = trig["push"]
        if spec is None:
            return True                      # `push:` with nothing under it
        if isinstance(spec, str):
            return True                      # `push: main` is a filter, but be strict
        if isinstance(spec, dict):
            return "branches" not in spec and "tags" not in spec
    return False


def main() -> int:
    # The guard must be able to fail: three shapes that must be flagged.
    assert unsafe("on:\n  push:\n    paths:\n      - 'a'\n"), "block form not detected"
    assert unsafe("on: {push: {paths: ['a']}}"), "flow form not detected"
    assert unsafe("on: push\n"), "bare `on: push` not detected"
    assert not unsafe("on:\n  push:\n    branches: [main]\n    paths:\n      - 'a'\n")
    assert not unsafe("on: {push: {branches: [main]}}")

    files = sorted(glob.glob(os.path.join(ROOT, ".github/workflows/*.yml")) +
                   glob.glob(os.path.join(ROOT, ".github/workflows/*.yaml")))
    bad = []
    for p in files:
        try:
            if unsafe(open(p, encoding="utf-8").read()):
                bad.append(os.path.basename(p))
        except yaml.YAMLError as e:
            print(f"FAIL: {os.path.basename(p)} is not valid YAML: {e}")
            return 1
    if bad:
        print(f"FAIL: {len(bad)} workflow(s) can be started by a tag push: {', '.join(bad)}")
        return 1
    print(f"ok   {len(files)} workflow file(s): every push trigger is limited to a branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
