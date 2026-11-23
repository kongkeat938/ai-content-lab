#!/usr/bin/env python3
"""No rail may build a clip below 4K. K (2026-11-23): "ต้อง 4k เท่านั้น ... อย่าพลาดอีก".

Every builder is imported for real and asked its own W/H -- a comment cannot be
checked, a constant can. A module that cannot be imported FAILS here too: a
builder whose deps are broken would otherwise slip past unmeasured.

    python3 scripts/test_all_builders_4k.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import upload_gate  # noqa: E402

# module -> orientation. Add a builder here when a new one appears; the test then
# holds it to 4K like the rest.
BUILDERS = {
    "video_grade": "long",
    "make_mv": "long",
    "make_chapter_video": "long",
    "make_night_video": "long",
    "make_kinetic_video": "long",
    "make_qa_video": "long",
    "make_short": "short",
    "make_motion_short": "short",
    "make_ambient_video": "short",
}

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def dims(module: str) -> tuple[int, int] | None:
    out = subprocess.run([sys.executable, "-c", f"import {module} as m; print(m.W, m.H)"],
                         cwd=HERE, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        print(f"     {module}: {out.stderr.strip().splitlines()[-1] if out.stderr else 'import failed'}")
        return None
    try:
        w, h = (int(x) for x in out.stdout.split())
    except ValueError:
        return None
    return w, h


def main() -> int:
    for module, kind in sorted(BUILDERS.items()):
        want_w, want_h = upload_gate.FOUR_K[kind]
        got = dims(module)
        check(got is not None and got[0] >= want_w and got[1] >= want_h,
              f"{module} builds {want_w}x{want_h} ({kind}) -- got {got}")
    print(f"\n{'FAILED' if failures else 'PASS'} ({len(failures)} failures)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
