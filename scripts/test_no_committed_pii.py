#!/usr/bin/env python3
"""The repo is PUBLIC: a real personal address must never be committed again.

K's channel addresses were scrubbed from the tree AND the history on 2026-11-15
(see scripts/test_no_committed_secrets.py for credentials). This guard keeps it
that way: any gmail-style address in a tracked file fails the build. The
deliberate placeholders (example.invalid) and the fixture `a@gmail.com` are
allowed, so the guard names exactly the case that must never return.

    python3 scripts/test_no_committed_pii.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A personal mailbox at a free provider. example.invalid is a placeholder and the
# test fixture is synthetic, so both are fine; anything else is a real address.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?:gmail|googlemail|hotmail|outlook|yahoo|icloud)\.[A-Za-z]+")
ALLOWED = {"a@gmail.com"}  # fixture in scripts/test_mail_credentials.py

TEXT_EXT = {".py", ".json", ".md", ".yml", ".yaml", ".sh", ".txt", ".html", ".css", ".js", ".toml", ".cfg", ".ini"}


def tracked_text_files() -> list[str]:
    out = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True).stdout.split()
    return [f for f in out if os.path.splitext(f)[1].lower() in TEXT_EXT]


def main() -> int:
    hits: list[str] = []
    for rel in tracked_text_files():
        path = os.path.join(ROOT, rel)
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for n, line in enumerate(fh, 1):
                    for m in EMAIL.findall(line):
                        if m.lower() not in ALLOWED:
                            hits.append(f"{rel}:{n}: {m}")
        except OSError:
            continue
    if hits:
        print("FAIL: a personal address is committed in the PUBLIC repo:")
        for h in hits:
            print("  " + h)
        print("Move it to the CH_ACCOUNTS secret and keep only example.invalid placeholders.")
        return 1
    print(f"OK: scanned {len(tracked_text_files())} tracked text files; no personal address")
    return 0


if __name__ == "__main__":
    sys.exit(main())
