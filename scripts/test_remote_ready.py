#!/usr/bin/env python3
"""The remote-in path must stay usable: the helper drives the browser, the launcher
self-heals after a pod recycle.

K does not want to click through Google ("ak ต้องรีโมท มาทำให้ K"). The one thing he
does is type a password on the VNC screen; ak drives the rest over CDP. If the helper
loses the Google "Next" handling, or the launcher stops reinstalling its tools after a
recycle, K is left staring at a dead screen. This locks both, and can FAIL.

    python3 scripts/test_remote_ready.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    helper = open(os.path.join(HERE, "remote_browser.py"), encoding="utf-8").read()
    launcher = open(os.path.join(HERE, "start_novnc.sh"), encoding="utf-8").read()

    print("the helper knows the Google Next control (clicking the span alone does nothing)")
    check("prefers [id$=Next]", "[id$=Next]" in helper)

    print("the helper exposes the four drives ak needs")
    for cmd in ("goto", "text", "click", "type", "shot"):
        check(f"command {cmd!r} present", f'"{cmd}"' in helper)

    print("the launcher self-heals after a recycle")
    check("reinstalls its tools when missing",
          "apt-get install" in launcher and "command -v" in launcher)
    check("serves noVNC on the work port", "websockify" in launcher)

    print("the runbook exists so K is not guessing")
    check("docs/REMOTE-2026-11-12.md present",
          os.path.exists(os.path.join(ROOT, "docs", "REMOTE-2026-11-12.md")))

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: ak can drive the browser K signs into")
    return 0


if __name__ == "__main__":
    sys.exit(main())
