#!/usr/bin/env python3
"""A long-form build must encode the 4K picture ONCE.

Measured 2026-11-26: two builds were killed at the 150-minute runner limit
because the picture was encoded three times (per-shot files, the crossfade, then
the title burn). A comment cannot hold that line, so this test counts the
encodes: one libx264 pass, then a stream copy for the mux.

    python3 scripts/test_longform_single_pass.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import longform_clip as lc

failures: list[str] = []
calls: list[list[str]] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main() -> int:
    lc.sc.duration = lambda path: 30.0          # no real audio file needed
    lc.sc.ff = lambda argv: calls.append(list(argv))
    lc.sc.mix = lambda narr, music, total, tmp: "/tmp/mix.wav"   # audio is measured elsewhere
    lc.build(["a.png", "b.png", "c.png"], "n.mp3", "m.wav", "title", "sub", "/tmp/o.mp4", "/tmp")

    encodes = [c for c in calls if "-c:v" in c and c[c.index("-c:v") + 1] == "libx264"]
    copies = [c for c in calls if "-c:v" in c and c[c.index("-c:v") + 1] == "copy"]
    check(len(encodes) == 1, f"exactly one picture encode (got {len(encodes)})")
    check(bool(copies), "the audio mux copies the picture instead of re-encoding it")
    graph = " ".join(encodes[0]) if encodes else ""
    check("xfade" in graph, "the crossfades happen inside that single pass")
    check("drawtext" in graph, "the titles are burned in that same pass")
    check("zoompan" in graph, "the Ken Burns move is part of it too")
    check("-preset" in graph and "veryfast" in graph, "the pass uses the measured preset")
    check(not [c for c in calls if "shot0.mp4" in " ".join(c)], "no per-shot intermediate files")

    print()
    if failures:
        print(f"FAILED: {len(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
