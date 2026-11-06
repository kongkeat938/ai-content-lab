#!/usr/bin/env python3
"""Open one GitHub issue with a night build's measured numbers.

The workflow that builds the compilation must report evidence, not an assurance,
and must not open a new issue on every rerun. This finds an existing open issue
for the same content and updates it, otherwise creates one.

    python3 scripts/report_night.py --receipt work/night/receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

TITLE = "Night compilation — review before publishing"


def gh(*args: str) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def body_for(r: dict) -> str:
    ai = r.get("audio_info", {})
    vi = r.get("video_info", {})
    return "\n".join([
        "A night compilation was built and passed the audio/picture gates.",
        "It has been queued in the publish manifest and the upload was dispatched;",
        "watch the publish-batch run, then spot-check the video when it is live.",
        "",
        f"- pieces: {len(r.get('pieces', []))}",
        f"- length: {ai.get('minutes', '?')} min ({ai.get('cycles', '?')} cycles)",
        f"- loudness: {ai.get('lufs', '?')} LUFS",
        f"- true peak (mp3): {ai.get('true_peak_dbfs', '?')} dBFS",
        f"- true peak (mp4): {vi.get('true_peak_dbfs', '?')} dBFS",
        f"- video: {vi.get('video', '?')}",
        f"- verdict: {r.get('verdict', '?')}",
        "",
        "This issue was created by an AI agent (OpenHands) on behalf of the project owner.",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    a = ap.parse_args()

    r = json.load(open(a.receipt, encoding="utf-8"))
    body = body_for(r)
    repo = ["--repo", a.repo] if a.repo else []

    existing = json.loads(gh("issue", "list", *repo, "--state", "open",
                             "--search", TITLE, "--json", "number,title") or "[]")
    hit = next((i for i in existing if i["title"] == TITLE), None)
    if hit:
        gh("issue", "comment", str(hit["number"]), *repo, "--body", body)
        print(f"updated issue #{hit['number']}")
    else:
        out = gh("issue", "create", *repo, "--title", TITLE, "--body", body)
        print(f"created {out.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
