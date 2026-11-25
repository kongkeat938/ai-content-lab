#!/usr/bin/env python3
"""The restore check must pass on a complete commit and FAIL on an incomplete one."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(ok: bool, label: str) -> None:
    global fails
    print(("  ok   " if ok else "  FAIL ") + label)
    if not ok:
        fails += 1


def run(repo: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "restore_verify.py"),
                           "--repo", repo], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def main() -> int:
    r = run(ROOT)
    check(r.returncode == 0, f"this repo restores from HEAD ({r.stdout.strip()[:120] or r.stderr.strip()[:120]})")

    # a repo that is missing the state must be caught, not silently accepted
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True, stdin=subprocess.DEVNULL)
        open(os.path.join(tmp, "README.md"), "w").write("only this\n")
        subprocess.run(["git", "-C", tmp, "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "-qm", "one file"], check=True, stdin=subprocess.DEVNULL)
        r = run(tmp)
        check(r.returncode == 1 and "not in the commit" in r.stdout,
              "REGRESSION: an incomplete commit FAILS the restore check")
    print("FAIL" if fails else "PASS", "test_restore_verify")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
