#!/usr/bin/env python3
"""git_push_retry.sh must resolve a racing conflict on an append-only ledger.

Measured 2026-11-13: ch4-longform committed its manifest, then git_push_retry.sh
rebased into a CONFLICT on content/bed_ledger_kongkeat.json and retried 5 times.
The ledger carries `merge=unionjson` in .gitattributes, but git only uses a custom
driver when it is registered in the repo's own config -- and only publish-shorts and
remake-shorts registered it. The finished video (already on a Release) was stranded.

This runs the real helper against a throwaway origin and proves both directions:
  * with the driver registered, the racing rebase unions the ledger and the push
    succeeds -- both records survive;
  * with the registration stripped (the 2026-11-13 state), the same rebase
    conflicts and the helper fails, so the test can FAIL.

    python3 scripts/test_push_retry_union.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HELPER = open(os.path.join(HERE, "git_push_retry.sh"), encoding="utf-8").read()
DRIVER = os.path.join(HERE, "git_union_merge.py")

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=check)


def clone(tmp, name):
    d = os.path.join(tmp, name)
    subprocess.run(["git", "clone", "--quiet", os.path.join(tmp, "origin.git"), d],
                   check=True, capture_output=True)
    git(d, "config", "user.name", "t")
    git(d, "config", "user.email", "t@t")
    os.makedirs(os.path.join(d, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(d, "content"), exist_ok=True)
    shutil.copy(DRIVER, os.path.join(d, "scripts", "git_union_merge.py"))
    return d


def write_ledger(d, vals):
    with open(os.path.join(d, "content", "bed_ledger_kongkeat.json"), "w", encoding="utf-8") as fh:
        json.dump({"beds": vals}, fh)


def read_ledger(d):
    with open(os.path.join(d, "content", "bed_ledger_kongkeat.json"), encoding="utf-8") as fh:
        return json.load(fh)["beds"]


def scenario(tmp, helper_text, label):
    """Return (push_returncode, unioned_values)."""
    origin = os.path.join(tmp, "origin.git")
    if not os.path.exists(origin):
        subprocess.run(["git", "init", "--bare", "--quiet", "-b", "main", origin], check=True)
    d = clone(tmp, "work")
    with open(os.path.join(d, ".gitattributes"), "w", encoding="utf-8") as fh:
        fh.write("content/bed_ledger_*.json merge=unionjson\n")
    write_ledger(d, ["a"])
    with open(os.path.join(d, "scripts", "git_push_retry.sh"), "w", encoding="utf-8") as fh:
        fh.write(helper_text)
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "init")
    git(d, "push", "-q", "origin", "main")

    # A concurrent rail commits a different bed to origin first.
    other = clone(tmp, "other")
    write_ledger(other, ["a", "b"])
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "other")
    git(other, "push", "-q", "origin", "main")

    # Our rail commits its own bed and then pushes through the helper.
    write_ledger(d, ["a", "c"])
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "ours")
    r = subprocess.run(["bash", "scripts/git_push_retry.sh"], cwd=d,
                       capture_output=True, text=True)
    print(f"  [{label}] helper exit {r.returncode}")
    if r.returncode != 0:
        return r.returncode, None
    verify = clone(tmp, "verify")
    return 0, read_ledger(verify)


def main() -> int:
    print("with the driver registered, a racing ledger conflict is unioned")
    tmp = tempfile.mkdtemp()
    try:
        rc, vals = scenario(tmp, HELPER, "registered")
        check("the helper pushed successfully", rc == 0, f"exit {rc}")
        check("both beds survived the racing push",
              vals is not None and sorted(vals) == ["a", "b", "c"], str(vals))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("without the registration (the 2026-11-13 state), the same push fails")
    tmp = tempfile.mkdtemp()
    stripped = "\n".join(l for l in HELPER.splitlines()
                         if "merge.unionjson.driver" not in l
                         and "merge.unionjson.name" not in l) + "\n"
    try:
        rc, vals = scenario(tmp, stripped, "stripped")
        check("the helper fails on the unmerged conflict", rc != 0, f"exit {rc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: the push helper unions a racing ledger conflict (and fails without it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
