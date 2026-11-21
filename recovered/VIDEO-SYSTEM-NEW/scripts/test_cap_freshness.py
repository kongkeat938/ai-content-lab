#!/usr/bin/env python3
"""The daily cap must be counted from origin/main at the moment of decision.

Measured 2026-11-20: the publish job wrote dharma's Short 123 at 03:43:53Z and
pushed the ledger at 03:43:55Z. The remake job of the SAME tick started at
03:44:00Z -- after that push landed -- but `actions/checkout` had pinned its tree
to the run's head_sha (log: `fetch --depth=1 origin +2daeca6 -> origin/main`), so
it read "2/3" from the pre-run snapshot and uploaded the 4th Short of the day one
minute after the third, against MIN_GAP_HOURS=2. The concurrency group worked; the
count was simply read from the wrong place.

What this locks, each of which can FAIL:

  1. **A stale working tree cannot undercount.** A real origin with three stamps
     and a working tree holding one must report 3. Reading the tree reports 1, and
     that is the bug.
  2. **An unreachable origin is a STOP, not a zero.** A fetch that fails must raise
     LedgerUnreadable. Returning 0 (or the stale number) is the false pass that
     turns a blind read into an over-cap upload.
  3. **`last_look` refuses at the cap and inside the gap**, so the check after the
     build cannot wave through a slot another rail already spent.
  4. **Every rail calls it before the upload**, swept from disk -- a new rail that
     forgets it fails here instead of at 3am. No hardcoded file list.

    python3 scripts/test_cap_freshness.py    # exit 0 = the cap is counted fresh
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as PS  # noqa: E402

FAILS: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + label + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(label)


def git(cwd: str, *args: str) -> None:
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr}")


def stamp(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def make_repos(tmp: str, remote_stamps: list[str], tree_stamps: list[str]) -> str:
    """A bare origin whose ledger has `remote_stamps`, and a clone whose working
    tree is stale -- exactly the shape of a CI checkout pinned to head_sha."""
    origin = os.path.join(tmp, "origin.git")
    git(tmp, "init", "--quiet", "--bare", "-b", "main", origin)
    seed = os.path.join(tmp, "seed")
    git(tmp, "clone", "--quiet", origin, seed)
    git(seed, "checkout", "--quiet", "-b", "main")
    os.makedirs(os.path.join(seed, "content"), exist_ok=True)
    with open(os.path.join(seed, "content", "upload_log.json"), "w", encoding="utf-8") as fh:
        json.dump({"channels": {"dharma": remote_stamps}}, fh)
    git(seed, "add", "-A")
    git(seed, "commit", "--quiet", "-m", "remote ledger")
    git(seed, "push", "--quiet", "origin", "main")

    work = os.path.join(tmp, "work")
    git(tmp, "clone", "--quiet", origin, work)
    # Rewind the working tree's ledger to an older count, as a pinned checkout is.
    with open(os.path.join(work, "content", "upload_log.json"), "w", encoding="utf-8") as fh:
        json.dump({"channels": {"dharma": tree_stamps}}, fh)
    return work


def main() -> int:
    old_log = PS.UPLOAD_LOG

    # 1. A stale tree must not undercount.
    print("\n1. the count comes from origin, not from the pinned working tree")
    with tempfile.TemporaryDirectory() as tmp:
        remote = [stamp(1), stamp(3), stamp(5)]
        work = make_repos(tmp, remote, [stamp(5)])
        local = json.load(open(os.path.join(work, "content", "upload_log.json")))
        check(len(local["channels"]["dharma"]) == 1, "the working tree really is stale")
        man = os.path.join(work, "content", "ch2_shorts.json")
        try:
            fresh = PS.uploads_in_last_24h("dharma", man, root=work)
        finally:
            pass
        check(fresh == 3, "a fresh read sees all three uploads from origin", f"got {fresh}")
        stale = PS.cap_state("dharma", man, fresh=False, root=work)[0]
        check(stale == 1, "the working-tree read is what the old code did (1)", f"got {stale}")

        # 2. An unreachable origin is a STOP, never a zero.
        print("\n2. an unreachable origin raises instead of reporting zero")
        git(work, "remote", "set-url", "origin", os.path.join(tmp, "gone.git"))
        raised = None
        try:
            PS.cap_state("dharma", man, root=work)
        except PS.LedgerUnreadable as exc:
            raised = exc
        check(raised is not None, "a failed fetch raises LedgerUnreadable",
              "returned a count -- a blind read would pass the cap")

    # 3. last_look refuses at the cap and inside the gap.
    print("\n3. the last look refuses a slot another rail already spent")
    with tempfile.TemporaryDirectory() as tmp:
        work = make_repos(tmp, [stamp(1), stamp(3), stamp(5)], [stamp(5)])
        man = os.path.join(work, "content", "ch2_shorts.json")
        ok, why = PS.last_look("dharma", man, root=work)
        check(not ok and "cap reached" in why, "cap full -> refused", why)
    with tempfile.TemporaryDirectory() as tmp:
        work = make_repos(tmp, [stamp(0.5)], [stamp(0.5)])
        man = os.path.join(work, "content", "ch2_shorts.json")
        ok, why = PS.last_look("dharma", man, root=work)
        check(not ok and "since the last upload" in why, "inside the gap -> refused", why)

    # 3b. `made` must UNION with the ledger, not be added to it or maxed against it.
    #     Added double-counts the moment the push lands; maxed undercounts while it
    #     has not, which is the same over-cap upload in a different disguise.
    print("\n3b. this run's own uploads are unioned with the ledger")
    with tempfile.TemporaryDirectory() as tmp:
        work = make_repos(tmp, [stamp(1), stamp(3)], [stamp(1), stamp(3)])
        man = os.path.join(work, "content", "ch2_shorts.json")
        mine = stamp(0.05)
        n_pending, _ = PS.cap_state("dharma", man, made=[mine], root=work)
        check(n_pending == 3, "pending push: ledger 2 + mine 1 = 3 (not maxed to 2)",
              f"got {n_pending}")
        # Now the push lands: the ledger contains my stamp too.
        with open(os.path.join(work, "content", "upload_log.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"channels": {"dharma": [stamp(1), stamp(3), mine]}}, fh)
        git(work, "add", "-A")
        git(work, "commit", "--quiet", "-m", "push lands")
        git(work, "push", "--quiet", "origin", "main")
        n_landed, _ = PS.cap_state("dharma", man, made=[mine], root=work)
        check(n_landed == 3, "after the push: still 3 (not double-counted to 4)",
              f"got {n_landed}")

    # 3c. A reader and a writer must agree on the ledger KEY. Measured 2026-11-20:
    #     every rail wrote the ledger under the slug, the foreman read it under the
    #     channel_id, so the gate saw 0 while the ledger held 4 and a full day still
    #     dispatched a remake. Swept from the source -- a new rail that invents its
    #     own key fails here.
    print("\n3c. every reader asks for the same key the writers use")
    with tempfile.TemporaryDirectory() as tmp:
        work = make_repos(tmp, [stamp(1)], [stamp(1)])
        man = os.path.join(work, "content", "ch2_shorts.json")
        slug_n = PS.uploads_in_last_24h("dharma", man, root=work)
        cid_n = PS.uploads_in_last_24h("UCM3QO5L_pmj34n1JVlbhh-w", man, root=work)
        check(slug_n == 1 and cid_n == 0,
              "the ledger is keyed by slug; a channel_id lookup sees nothing",
              f"slug={slug_n} cid={cid_n}")
    writers = [p for p in glob.glob(os.path.join(HERE, "*.py"))
               if not os.path.basename(p).startswith("test_")
               and "note_upload(" in open(p, encoding="utf-8").read()]
    check(bool(writers), "found the writers by sweeping for note_upload(",
          str([os.path.basename(w) for w in writers]))
    for path in writers:
        src = open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        check(not re.search(r"note_upload\(\s*spec\[[\"']channel_id", src),
              f"{name}: records under the slug, never the channel_id")

    # The same rule at every CALL SITE, swept from disk. Testing the function in
    # isolation is not enough: the foreman read `_cid` and the gate was dead while
    # the function itself was correct (measured 2026-11-20).
    readers = [p for p in glob.glob(os.path.join(HERE, "*.py"))
               if not os.path.basename(p).startswith("test_")
               and re.search(r"(uploads_in_last_24h|hours_since_last_upload|last_look)\(",
                             open(p, encoding="utf-8").read())]
    check(bool(readers), "found the readers by sweeping the source",
          str([os.path.basename(r) for r in readers]))
    bad_key = re.compile(r"(?:uploads_in_last_24h|hours_since_last_upload|last_look)\(\s*"
                         r"(?:_?cid\b|spec\[[\"']channel_id|[\"']UC[\w-]+[\"'])")
    for path in readers:
        name = os.path.basename(path)
        hits = bad_key.findall(open(path, encoding="utf-8").read())
        check(not hits, f"{name}: never asks for the ledger under a channel_id",
              f"{len(hits)} call site(s)")

    # 3d. A channel with NO ledger entry is not a channel with no uploads. The
    #     manifest carries the exact time, and a remake (recorded in the _remakes
    #     manifest) spends a cap slot too. Measured 2026-11-20: reading only the
    #     primary manifest gave dharma 2 against a true 4, and the old seed wrote
    #     that wrong number into the ledger as fact.
    print("\n3d. a silent ledger falls back to the manifests, remakes included")
    with tempfile.TemporaryDirectory() as tmp:
        work = make_repos(tmp, [], [])
        man = os.path.join(work, "content", "ch2_shorts.json")
        rem = os.path.join(work, "content", "ch2_shorts_remakes.json")
        with open(man, "w", encoding="utf-8") as fh:
            json.dump({"shorts": {"a": {"posted_at": stamp(1)},
                                  "b": {"posted_at": stamp(2)}}}, fh)
        with open(rem, "w", encoding="utf-8") as fh:
            json.dump({"shorts": {"c": {"remade_at": stamp(3)}}}, fh)
        n, _ = PS.cap_state("dharma", man, root=work)
        check(n == 3, "no ledger entry -> 2 posts + 1 remake = 3, not 0", f"got {n}")
        check(not PS._manifest_stamps(os.path.join(work, "content", "nope.json")),
              "a missing manifest contributes nothing instead of raising")
    #    The set is swept from the source: a file that inserts a video AND counts
    #    the Shorts cap is a Shorts rail. Long-form rails (publish_batch,
    #    publish_youtube) are not, and carry no cap to keep fresh.
    print("\n4. every uploading rail re-checks before the byte moves")
    rails = sorted(p for p in glob.glob(os.path.join(HERE, "*.py"))
                   if not os.path.basename(p).startswith("test_")
                   and "videos().insert" in open(p, encoding="utf-8").read()
                   and "DAILY_CAP" in open(p, encoding="utf-8").read())
    check(len(rails) >= 3, "found the Shorts rails by sweeping the source",
          f"{len(rails)}: {[os.path.basename(r) for r in rails]}")
    for path in rails:
        src = open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        i_look = src.find("last_look(")
        i_ins = src.find("videos().insert")
        check(0 <= i_look < i_ins, f"{name}: last_look() runs before videos().insert",
              f"look@{i_look} insert@{i_ins}")
        check("LedgerUnreadable" in src, f"{name}: handles an unreadable ledger")

    PS.UPLOAD_LOG = old_log
    print()
    if FAILS:
        print(f"FAILED {len(FAILS)}:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("PASS -- the cap is counted from origin/main at decision time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
