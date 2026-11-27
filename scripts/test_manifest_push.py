#!/usr/bin/env python3
"""The manifest push must survive the clone the rails actually give it.

Measured 2026-11-27: three publish-shorts runs uploaded their Short, then lost the
id at `git pull --rebase` (exit 128). The rails check out with `fetch-depth: 1`,
and a shallow clone has no merge base to rebase onto -- so every retry failed the
same way, the ledger kept no id, and the next audit called the live clips rogue.

    python3 scripts/test_manifest_push.py
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


class Recorder:
    """Stands in for subprocess.run and records every argv it is handed."""

    def __init__(self, shallow="true", pull_fails=0, push_fails=0):
        self.calls = []
        self.shallow, self.pull_fails, self.push_fails = shallow, pull_fails, push_fails

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        rc = 0
        joined = " ".join(argv)
        if "rev-parse --is-shallow-repository" in joined:
            out = types.SimpleNamespace(returncode=0, stdout=self.shallow + "\n", stderr="")
            return out
        if "diff --cached --quiet" in joined:
            rc = 1                      # something is staged: do not early-return
        if "pull" in argv and "--rebase" in argv and self.pull_fails:
            self.pull_fails -= 1
            rc = 128                    # what a shallow clone actually returns
        if argv[:1] == ["git"] and "push" in argv and self.push_fails:
            self.push_fails -= 1
            rc = 1
        return types.SimpleNamespace(returncode=rc, stdout="", stderr="")

    def flat(self):
        return [" ".join(c) for c in self.calls]


def run_commit(rec, monkey_git_env=True):
    orig_run, orig_env = ps.subprocess.run, os.environ.get("GITHUB_ACTIONS")
    ps.subprocess.run = rec
    if monkey_git_env:
        os.environ["GITHUB_ACTIONS"] = "true"
    try:
        ps.commit(os.path.join(ROOT, "content", "ch2_shorts.json"), "test")
    finally:
        ps.subprocess.run = orig_run
        if orig_env is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = orig_env


def main() -> int:
    # 1. a shallow checkout is deepened BEFORE the first rebase, or the rebase
    #    fails for a reason no retry can fix
    rec = Recorder(shallow="true")
    run_commit(rec)
    flat = rec.flat()
    deepen = [i for i, c in enumerate(flat) if "--unshallow" in c]
    rebase = [i for i, c in enumerate(flat) if "pull --rebase" in c]
    check("the shallow clone is deepened", bool(deepen), str(flat[:4]))
    check("deepening happens before the rebase",
          bool(deepen) and bool(rebase) and deepen[0] < rebase[0], str(flat[:5]))

    # 2. a rebase that still fails is retried, and the broken rebase is aborted
    rec = Recorder(shallow="true", pull_fails=2)
    run_commit(rec)
    flat = rec.flat()
    check("a failed rebase is retried", len([c for c in flat if "pull --rebase" in c]) >= 3,
          str([c for c in flat if "pull --rebase" in c]))
    check("the broken rebase is aborted", any("rebase --abort" in c for c in flat), str(flat[-6:]))
    check("it eventually pushes", any(c.endswith("git push") or c == "git push" for c in flat))

    # 3. an unpushable ledger must say so, and must not crash the upload that
    #    already happened
    rec = Recorder(shallow="false", push_fails=99)
    run_commit(rec)
    flat = rec.flat()
    check("push is retried, not given up on the first rejection",
          len([c for c in flat if c == "git push"]) >= 2, str([c for c in flat if c == "git push"]))

    # 4. a deep clone is not deepened again (the extra fetch costs a minute)
    rec = Recorder(shallow="false")
    run_commit(rec)
    check("a deep clone skips the unshallow", not any("--unshallow" in c for c in rec.flat()),
          str(rec.flat()[:3]))

    # 5. outside CI nothing is committed at all
    rec = Recorder()
    orig_run = ps.subprocess.run
    ps.subprocess.run = rec
    os.environ.pop("GITHUB_ACTIONS", None)
    try:
        ps.commit("content/ch2_shorts.json", "test")
    finally:
        ps.subprocess.run = orig_run
    check("no git work outside CI", not rec.calls, str(rec.flat()))

    bad = [n for n, ok, _ in CHECKS if not ok]
    print()
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed" if not bad
          else f"FAIL: {len(bad)} check(s): {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
