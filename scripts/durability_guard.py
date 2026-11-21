#!/usr/bin/env python3
"""Durability guard: work that lives only in the pod is lost on recycle.

The pod is recycled often (see MEMORY). Every loss had one shape -- the code, the
approved demo, or the vault lived only in the pod's working tree or /tmp and was
never pushed. This guard turns that state into a FAILURE instead of silence.

    python3 scripts/durability_guard.py        # exit 0 = everything is durable

It measures the real repo (not a doc):
  1. no uncommitted change (git status --porcelain is empty),
  2. no unpushed commit (HEAD is not ahead of its upstream),
  3. critical state is tracked (the vault index, the warehouse queue) -- a file
     that exists but is untracked would be lost on the next recycle.

A session must run this before it ends; a rail runs it too. In CI (env CI set)
the unpushed check is skipped because CI never pushes and has no upstream.
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# State that must be in git or a recycle destroys it. Only checked when the file
# exists: a missing vault is fine, a vault that is present but untracked is not.
CRITICAL_TRACKED = ("content/image_vault.json", "assets/queue/index.json")


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )


def check(root: str = ROOT, allow_no_upstream: bool | None = None) -> list[str]:
    """Return the list of durability failures (empty == durable)."""
    if allow_no_upstream is None:
        allow_no_upstream = bool(os.environ.get("CI"))

    fails: list[str] = []

    status = _git(root, "status", "--porcelain").stdout.strip()
    if status:
        lines = status.splitlines()
        fails.append(
            f"{len(lines)} uncommitted change(s) -- commit and push, the pod will "
            "be recycled:\n" + "\n".join("    " + ln for ln in lines[:20])
        )

    upstream = _git(root, "rev-parse", "--abbrev-ref",
                    "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        if not allow_no_upstream:
            fails.append(
                "no upstream tracking branch -- commits have nowhere to be pushed"
            )
    else:
        ahead = _git(root, "rev-list", "--count", "@{u}..HEAD").stdout.strip()
        try:
            n = int(ahead)
        except ValueError:
            n = 0
        if n > 0:
            fails.append(f"{n} commit(s) not pushed -- run `git push`")

    for rel in CRITICAL_TRACKED:
        if os.path.exists(os.path.join(root, rel)):
            tracked = _git(root, "ls-files", "--error-unmatch", rel)
            if tracked.returncode != 0:
                fails.append(
                    f"{rel} exists but is untracked -- it will be lost on recycle"
                )
    return fails


def main() -> int:
    fails = check()
    if fails:
        print("FAIL -- work is NOT durable (a pod recycle would lose it):")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS -- no uncommitted/unpushed work; critical state is tracked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
