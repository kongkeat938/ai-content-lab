#!/usr/bin/env python3
"""Prove the durability guard can FAIL -- a happy-path check proves nothing.

Builds a throwaway repo with a bare remote and drives every failure mode:
uncommitted change, unpushed commit, an untracked critical file, and a repo
with no upstream. If any mode stops failing, this test fails.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import durability_guard as G


def sh(*args: str, cwd: str) -> None:
    subprocess.run(args, cwd=cwd, check=True,
                   capture_output=True, stdin=subprocess.DEVNULL)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="durab-")
    bare = os.path.join(tmp, "remote.git")
    work = os.path.join(tmp, "work")
    sh("git", "init", "--bare", "-b", "main", bare, cwd=tmp)
    os.makedirs(work)
    sh("git", "init", "-b", "main", work, cwd=work)
    sh("git", "config", "user.email", "t@t", cwd=work)
    sh("git", "config", "user.name", "t", cwd=work)
    sh("git", "config", "commit.gpgsign", "false", cwd=work)
    with open(os.path.join(work, "a.txt"), "w") as fh:
        fh.write("x\n")
    sh("git", "add", "-A", cwd=work)
    sh("git", "commit", "-m", "a", cwd=work)
    sh("git", "remote", "add", "origin", bare, cwd=work)
    sh("git", "push", "-u", "origin", "main", cwd=work)

    fails = []

    # A) clean and pushed -> durable
    got = G.check(work, allow_no_upstream=False)
    if got:
        fails.append(f"A clean+pushed should pass, got {got}")

    # B) uncommitted change -> must fail
    with open(os.path.join(work, "b.txt"), "w") as fh:
        fh.write("y\n")
    got = G.check(work, allow_no_upstream=False)
    if not any("uncommitted" in f for f in got):
        fails.append(f"B untracked change not caught: {got}")
    os.remove(os.path.join(work, "b.txt"))

    # C) unpushed commit -> must fail
    with open(os.path.join(work, "a.txt"), "w") as fh:
        fh.write("x2\n")
    sh("git", "commit", "-am", "b", cwd=work)
    got = G.check(work, allow_no_upstream=False)
    if not any("not pushed" in f for f in got):
        fails.append(f"C unpushed commit not caught: {got}")
    sh("git", "push", cwd=work)

    # D) critical file present but untracked -> must fail
    os.makedirs(os.path.join(work, "content"))
    with open(os.path.join(work, "content", "image_vault.json"), "w") as fh:
        fh.write("{}\n")
    got = G.check(work, allow_no_upstream=False)
    if not any("image_vault" in f for f in got):
        fails.append(f"D untracked critical file not caught: {got}")

    # E) no upstream: fail by default, skipped only when allowed
    nob = os.path.join(tmp, "noup")
    os.makedirs(nob)
    sh("git", "init", "-b", "main", nob, cwd=nob)
    sh("git", "config", "user.email", "t@t", cwd=nob)
    sh("git", "config", "user.name", "t", cwd=nob)
    with open(os.path.join(nob, "z.txt"), "w") as fh:
        fh.write("z\n")
    sh("git", "add", "-A", cwd=nob)
    sh("git", "commit", "-m", "z", cwd=nob)
    if not any("upstream" in f for f in G.check(nob, allow_no_upstream=False)):
        fails.append("E no-upstream not caught when it should be")
    if G.check(nob, allow_no_upstream=True):
        fails.append("E no-upstream should be allowed for CI")

    if fails:
        print("FAIL -- the durability guard stopped failing on a real loss mode:")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS -- durability guard fails on every loss mode (dirty, unpushed, "
          "untracked-critical, no-upstream)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
