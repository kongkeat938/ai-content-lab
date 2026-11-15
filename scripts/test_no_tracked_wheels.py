#!/usr/bin/env python3
"""Fail if a built package artifact (a .whl, sdist, or other binary blob) is tracked.

Measured 2026-11-15: commit afabc656 swept 31 Python `.whl` files (9.2 MB, e.g.
cryptography-50, pygments, rich) into the repo ROOT. Nothing in the repo referenced
any of them -- `requirements.txt` installs from pip -- so they were pure dead weight
in a PUBLIC repo (slower clone, larger .git on every touch). They came in because a
broad `git add` picked up a scratch `pip download` directory.

The repo legitimately tracks media (poster .jpg/.png, .mp3/.mp4 under site/), so the
rule is narrow: no *packaging/executable* artifact may be tracked. This guard can
FAIL -- `git add some.whl` and it exits 1.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Built package + native/executable artifacts. Deliberately NOT media.
BAD_EXT = {
    ".whl", ".egg", ".tar.gz", ".tgz", ".zip", ".jar", ".deb", ".rpm", ".msi",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".class", ".pyc", ".pyd",
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", ROOT, "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def has_bad_ext(rel: str) -> bool:
    low = rel.lower()
    return any(low.endswith(ext) for ext in BAD_EXT)


def main() -> int:
    tracked = tracked_files()
    offenders = [rel for rel in tracked if has_bad_ext(rel)]
    if offenders:
        preview = ", ".join(offenders[:10])
        more = "" if len(offenders) <= 10 else f" (+{len(offenders) - 10} more)"
        fail(f"{len(offenders)} built-package/binary artifact(s) are tracked: "
             f"{preview}{more}. Remove them with `git rm --cached` and add the "
             f"pattern to .gitignore -- these do not belong in the repo.")

    # The guard must actually be able to see a wheel; prove the rule bites by
    # checking a synthetic name rather than trusting an empty real list.
    if not has_bad_ext("example-1.0-py3-none-any.whl"):
        fail("guard is broken: it does not recognise a .whl")

    print(f"OK: no built-package/binary artifact is tracked ({len(tracked)} files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
