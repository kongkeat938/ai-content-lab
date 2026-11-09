#!/usr/bin/env python3
"""Catch a git conflict that was committed instead of resolved.

Measured 2026-11-09: a `git pull --rebase --autostash` in remake-shorts left
conflict markers inside content/upload_log.json and the markers got committed
(612f185). Every foreman run then crashed on the unparsable JSON, so no rail
was driven from the chain until it was found. Two properties lock that out:

  1. No tracked text file may contain a conflict marker. A marker means a merge
     was committed unresolved, which is always a bug.
  2. Every JSON file the rails read must parse. A committed marker breaks
     json.load, and a broken ledger silently stops a cap from being counted.
  3. Every workflow that runs `git push` must `git pull --rebase` first. Rails run
     concurrently and all commit to main, so a push onto a stale base is rejected
     -- measured 2026-11-09: fetch-music.yml was the only workflow without the
     rebase and its push failed against a foreman push (the same race that, in the
     foreman itself, once committed conflict markers).

    python3 scripts/test_repo_hygiene.py     # exit 0 = no committed conflict
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A real conflict marker sits at the start of a line. Anchoring there keeps a
# detector's own string literal (e.g. publish_shorts.py's "<<<<<<< ") from
# tripping this guard.
MARKER_RE = re.compile(r"^(<{7} |>{7} )", re.M)
TEXT_EXT = {".py", ".json", ".md", ".yml", ".yaml", ".sh", ".txt", ".html", ".css", ".js"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", ROOT, "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def main() -> int:
    bad = []
    json_bad = []
    for rel in tracked_files():
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        path = os.path.join(ROOT, rel)
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if MARKER_RE.search(text):
            bad.append(rel)
        if rel.endswith(".json"):
            try:
                json.loads(text)
            except ValueError as exc:
                json_bad.append(f"{rel}: {exc}")

    if bad:
        fail(f"committed conflict markers in: {', '.join(bad)} -- resolve and "
             "re-commit; a marker means a merge landed unresolved")
    if json_bad:
        fail("unparsable JSON: " + "; ".join(json_bad) + " -- a rail that reads "
             "this file will crash, as the foreman did on 2026-11-09")

    # A workflow that pushes must rebase first, or it races every other rail that
    # commits to main. Skip a push in a workflow_dispatch-only path that never
    # lands on main? None exist; every `git push` here writes main.
    #
    # Rebasing alone is not enough: the race is *between* the rebase and the push,
    # so a single `pull --rebase; push` still loses when another rail commits in
    # that window. Measured 2026-11-09: that exact window failed night-compilation
    # ("cannot lock ref ... is at X but expected Y") and stranded a built video
    # (issue #21). Every push must therefore go through the retry helper, which
    # re-pulls and re-pushes on rejection.
    racy = []
    wf_dir = os.path.join(ROOT, ".github", "workflows")
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        text = open(os.path.join(wf_dir, name), encoding="utf-8").read()
        # Ignore comments so a prose mention of "git push" does not count.
        code = "\n".join(l for l in text.splitlines()
                         if not l.lstrip().startswith("#"))
        if "git push" not in code:
            continue
        if "git pull --rebase" not in code:
            racy.append(name)
        elif "git_push_retry.sh" not in code:
            racy.append(name + " (no retry)")
    if racy:
        fail(f"these workflows push without a rebase+retry: {', '.join(racy)} -- "
             "a concurrent rail will reject a single push; use "
             "`bash scripts/git_push_retry.sh` (it rebases and retries)")

    # Two hand-off traps measured 2026-11-09, both of which strand a finished
    # video with no error anyone sees:
    #   4. A release that omits receipt.json cannot be re-graded. A recovery run
    #      (build skipped) has no local receipt, so qa_gate sees an empty one and
    #      writes state=blocked -- a false veto. The release MUST carry the receipt.
    #   5. A hook file that is not in the build fingerprint means editing the hook
    #      does not change the tag, so the rail reuses the old release and never
    #      rebuilds with the fix.
    missing_receipt = []
    hook_untracked = []
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        text = open(os.path.join(wf_dir, name), encoding="utf-8").read()
        if "gh release create" not in text:
            continue
        # The release command is a set of lines joined by trailing backslashes
        # (create ... || upload ...). Collect that block and check the receipt is
        # among the uploaded assets -- a bare "receipt.json" elsewhere in the file
        # (e.g. the --receipt arg to add_release_to_manifest) must not satisfy it.
        lines = text.splitlines()
        block = []
        for i, ln in enumerate(lines):
            if "gh release create" in ln:
                block = [ln]
                j = i
                while lines[j].rstrip().endswith("\\") and j + 1 < len(lines):
                    j += 1
                    block.append(lines[j])
                break
        block_text = "\n".join(block)
        for rec in re.findall(r"--receipt\s+(\S+\.json)", text):
            if os.path.basename(rec) not in block_text:
                missing_receipt.append(f"{name}: {rec}")
        for hook in re.findall(r"--hook-file\s+(\S+\.md)", text):
            fp_block = text.split("fp=\"$(cat", 1)
            in_fp = len(fp_block) > 1 and hook in fp_block[1].split("|", 1)[0]
            if not in_fp:
                hook_untracked.append(f"{name}: {hook}")
    if missing_receipt:
        fail("these releases omit the receipt the hand-off needs to re-grade: "
             + ", ".join(missing_receipt) + " -- add the receipt to `gh release "
             "create`/`upload`, or a recovery run will false-veto the video")
    if hook_untracked:
        fail("these hook files are not in the build fingerprint, so a hook edit "
             "will not rebuild: " + ", ".join(hook_untracked) + " -- add the hook "
             "path to the `fp=\"$(cat ...)` block")

    # 6. `channel_overhaul.py --only playlists` silently skips the trailer step.
    #    Measured 2026-11-09: every rail called it that way, so NO channel had an
    #    `unsubscribedTrailer` -- the clip a non-subscriber sees first, and a direct
    #    subscribe lever -- sitting unused. The trailer must be set, so forbid the
    #    playlists-only form.
    no_trailer = []
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        text = open(os.path.join(wf_dir, name), encoding="utf-8").read()
        if "channel_overhaul.py" not in text:
            continue
        for ln in text.splitlines():
            if ln.lstrip().startswith("#"):
                continue
            if "--only playlists" in ln:
                no_trailer.append(name)
                break
    if no_trailer:
        fail("these workflows run channel_overhaul with `--only playlists`, which "
             "skips the trailer: " + ", ".join(no_trailer) + " -- drop the --only "
             "so the channel gets an unsubscribedTrailer")

    print(f"OK: no conflict markers, all JSON parses, every pushing workflow "
          f"rebases, releases carry the receipt, hooks are fingerprinted, trailers "
          f"are wired ({len(tracked_files())} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
