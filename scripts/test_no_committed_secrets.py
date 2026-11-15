#!/usr/bin/env python3
"""No tracked file may contain a live credential.

The repository is PUBLIC. The one leak class that actually bites is a refresh
token or client secret committed by accident -- an OAuth token already leaked
once and a third party used it to upload to our channels (issue #30). A secret
that reaches git history is disclosed the moment it lands, and deleting it later
does not take that back, so this guard refuses the commit instead.

It scans every tracked text file for the SHAPE of a real credential: a Google
OAuth refresh/access token, an API key, a GitHub PAT, a PEM private key, and the
common vendor prefixes. It is deliberately high-precision -- a placeholder like
`xxxx xxxx xxxx xxxx` or the word "token" must not trip it, or it becomes a
false-alarm machine and gets ignored.

It can FAIL: append a line holding a fake token to any tracked file and the scan
exits 1.

    python3 scripts/test_no_committed_secrets.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (label, pattern). Every pattern must match a credential and nothing else.
PATTERNS = [
    ("google oauth refresh token", re.compile(r"1//0[0-9A-Za-z_-]{20,}")),
    ("google oauth access token", re.compile(r"ya29\.[0-9A-Za-z_-]{20,}")),
    ("google api key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("google oauth client secret", re.compile(r"GOCSPX-[0-9A-Za-z_-]{20,}")),
    ("github token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("github fine-grained pat", re.compile(r"github_pat_[0-9A-Za-z_]{22,}")),
    ("slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("stripe secret", re.compile(r"[sr]k_live_[0-9A-Za-z]{20,}")),
]

TEXT_EXT = {".py", ".json", ".md", ".yml", ".yaml", ".sh", ".txt", ".html",
            ".css", ".js", ".toml", ".cfg", ".ini", ".env", ".ts"}
# Files whose whole job is to describe credential SHAPES; a doc may quote a
# pattern. Keep the allowlist explicit and short so it cannot grow silently.
ALLOW = set()


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", ROOT, "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def main() -> int:
    hits = []
    scanned = 0
    for rel in tracked_files():
        if rel in ALLOW or os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        try:
            text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        for label, rx in PATTERNS:
            for m in rx.finditer(text):
                hits.append(f"{rel}: {label} ({m.group(0)[:12]}...)")

    if hits:
        fail("a credential is committed to a PUBLIC repo: " + "; ".join(hits)
             + " -- revoke it now, then purge it from history (git filter-repo); "
             "removing the line alone does not undo the disclosure")

    print(f"OK: scanned {scanned} tracked text files; no credential shape found "
          f"({len(PATTERNS)} signatures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
