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


def real_git_round_trip() -> list[tuple[str, bool, str]]:
    """The same push against real git: a dirty tree must not block the rebase.

    The recorder above proves the argv order; this proves the outcome. It builds
    a bare origin, a racing commit from a second clone, then runs commit() with
    the run's other ledger writes still unstaged -- the exact state that printed
    "cannot pull with rebase: You have unstaged changes" on 2026-11-27.
    """
    import json
    import subprocess
    import tempfile

    def git(*a, cwd=None):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)

    out = []
    tmp = tempfile.mkdtemp(prefix="manifest-")
    try:
        origin = os.path.join(tmp, "origin.git")
        git("init", "--bare", "-q", "-b", "main", origin)
        seed = os.path.join(tmp, "seed")
        git("clone", "-q", origin, seed)
        for rel, body in (("content/ch2_shorts.json", '{"shorts": {}}'),
                          ("content/art_ledger_dharma.json", '{"items": {}}'),
                          ("content/upload_log.json", '{"uploads": []}')):
            path = os.path.join(seed, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(body)
        git("add", "-A", cwd=seed)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)

        work = os.path.join(tmp, "work")          # the rail's checkout, deep
        git("clone", "-q", origin, work)

        racer = os.path.join(tmp, "racer")        # the other channel's job
        git("clone", "-q", origin, racer)
        open(os.path.join(racer, "content", "other.json"), "w").write("{}")
        git("add", "-A", cwd=racer)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "racer", cwd=racer)
        git("push", "-q", "origin", "HEAD:main", cwd=racer)

        # this run: the id landed, and the art/bed/reception ledgers are dirty
        open(os.path.join(work, "content", "ch2_shorts.json"), "w").write(
            '{"shorts": {"135": {"video_id": "zlgdIGRvt6Y"}}}')
        open(os.path.join(work, "content", "art_ledger_dharma.json"), "w").write(
            '{"items": {"135": "abc"}}')

        saved = (ps.ROOT, ps.UPLOAD_LOG, os.environ.get("GITHUB_ACTIONS"))
        ps.ROOT = work
        ps.UPLOAD_LOG = os.path.join(work, "content", "upload_log.json")
        os.environ["GITHUB_ACTIONS"] = "true"
        try:
            ps.commit(os.path.join(work, "content", "ch2_shorts.json"),
                      "publish(dharma): record Short 135")
        finally:
            ps.ROOT, ps.UPLOAD_LOG, env = saved[0], saved[1], saved[2]
            if env is None:
                os.environ.pop("GITHUB_ACTIONS", None)
            else:
                os.environ["GITHUB_ACTIONS"] = env

        log = git("log", "--format=%s", "origin/main", cwd=work).stdout.split("\n")
        files = git("ls-tree", "-r", "--name-only", "origin/main", cwd=work).stdout.split()
        body = git("show", "origin/main:content/ch2_shorts.json", cwd=work).stdout
        out.append(("the id reaches origin despite a dirty tree",
                    "publish(dharma): record Short 135" in log, str(log[:4])))
        out.append(("the racing job's commit is kept", "racer" in log, str(log[:4])))
        out.append(("the run's other ledger writes go in the same commit",
                    "content/art_ledger_dharma.json" in files, str(files[:5])))
        out.append(("the manifest on origin carries the id", "zlgdIGRvt6Y" in body, body[:80]))
        out.append(("the tree is left clean",
                    git("status", "--porcelain", cwd=work).stdout.strip() == "",
                    git("status", "--porcelain", cwd=work).stdout[:120]))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return out


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

    # 6. the real thing: a dirty tree, a racing job, one push
    for name, ok, detail in real_git_round_trip():
        check(name, ok, detail)

    bad = [n for n, ok, _ in CHECKS if not ok]
    print()
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed" if not bad
          else f"FAIL: {len(bad)} check(s): {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
