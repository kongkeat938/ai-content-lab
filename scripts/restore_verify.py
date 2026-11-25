#!/usr/bin/env python3
"""Can this project be rebuilt from what is committed?

A pod reset wipes pip packages, /tmp and the working tree; only what is in a
commit survives. This exports the committed tree of a repository into an empty
directory -- the closest thing to "a fresh machine" we can do without a second
host -- and checks that the state the business depends on is in there.

    python3 scripts/restore_verify.py                  # this repo, HEAD
    python3 scripts/restore_verify.py --repo /path --ref HEAD

Exit 0 = every required piece is in the commit. Exit 1 = something is missing
(that file is lost on the next reset). Exit 2 = git could not read the repo.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = [
    "requirements.txt",
    "docs/OFFER-2026-11-25.md",
    "docs/PROJECT-MAP.md",
    "content/prospects.json",
    "scripts/shorts_from_long.py",
    "scripts/short_standard.py",
    "scripts/upload_gate.py",
    "scripts/deliver.py",
    "scripts/outreach_log.py",
    "scripts/prospect_score.py",
    "scripts/run_tests.py",
    "scripts/test_workflow_tag_safe.py",
    "scripts/test_outreach_log.py",
    "scripts/test_deliver.py",
    ".github/workflows/tests.yml",
    ".github/workflows/prospect-daily.yml",
    "content/packages.json",
    "content/prospects_external.json",
    "scripts/prospect_discover.py",
    "scripts/proposal_draft.py",
    "scripts/build_portfolio.py",
    "scripts/make_samples.py",
    "scripts/net_revenue.py",
    "docs/portfolio/index.html",
    "assets/fonts/NotoSansThai.ttf",
]


def export(repo: str, ref: str, dest: str) -> None:
    archive = subprocess.run(["git", "-C", repo, "archive", ref], capture_output=True,
                             stdin=subprocess.DEVNULL)
    if archive.returncode != 0:
        raise SystemExit(f"2: git archive failed in {repo}: {archive.stderr.decode()[:200]}")
    # A file, not a pipe: `input=` and `stdin=` cannot both be given, and the
    # guard requires stdin= on every child.
    tarball = os.path.join(dest, ".tree.tar")
    with open(tarball, "wb") as fh:
        fh.write(archive.stdout)
    tar = subprocess.run(["tar", "-xf", tarball, "-C", dest], capture_output=True,
                         stdin=subprocess.DEVNULL)
    os.remove(tarball)
    if tar.returncode != 0:
        raise SystemExit(f"2: tar failed: {tar.stderr.decode()[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=ROOT)
    ap.add_argument("--ref", default="HEAD")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        export(a.repo, a.ref, tmp)
        missing = [p for p in REQUIRED if not os.path.exists(os.path.join(tmp, p))]
        if missing:
            print(f"FAIL: {len(missing)} required piece(s) are not in the commit:")
            for m in missing:
                print(f"       {m}")
            print("      (uncommitted work is lost on the next pod reset)")
            return 1
        # a restored tree must actually run, not just exist
        r = subprocess.run([sys.executable, os.path.join(tmp, "scripts", "test_workflow_tag_safe.py")],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=tmp)
        if r.returncode != 0:
            print(f"FAIL: the restored tree cannot run its own guard: {r.stdout[-300:]}{r.stderr[-300:]}")
            return 1
        r = subprocess.run([sys.executable, os.path.join(tmp, "scripts", "outreach_log.py"), "report"],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=tmp,
                           env=dict(os.environ, OUTREACH_STORE=os.path.join(tmp, "outreach.json")))
        if r.returncode != 0:
            print(f"FAIL: the restored tree cannot run the ledger: {r.stderr[-300:]}")
            return 1
        print(f"ok   {len(REQUIRED)} required piece(s) restored from {a.repo}@{a.ref}, and they run")
        return 0


if __name__ == "__main__":
    sys.exit(main())
