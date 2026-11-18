#!/usr/bin/env python3
"""Guard: a Gemini reply must be read by joining EVERY part, never parts[0] alone.

Measured 2026-11-18: a live `generateContent` reply came back with two parts and a
reader taking `parts[0]["text"]` returned a string cut mid-word -- the API still
said `finishReason: STOP`, so the loss was silent and looked like a short answer.
Nine call sites had that shape. This guard sweeps the source (never a hardcoded
file list) for the raw `parts"][0]["text"]` read and FAILs if one is left, and it
proves `gemini_text.text_of` joins a split reply.

    python3 scripts/test_gemini_text.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gemini_text  # noqa: E402

# The exact shape that drops the tail: index the first part then read its text.
RAW_READ = re.compile(r'["\']parts["\']\s*\]\s*\[\s*0\s*\]\s*\[\s*["\']text["\']\s*\]')


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def test_text_of_joins_every_part():
    data = {"candidates": [{"content": {"parts": [{"text": "ครึ่งแรก"}, {"text": "ครึ่งหลัง"}]}}]}
    got = gemini_text.text_of(data)
    if got != "ครึ่งแรกครึ่งหลัง":
        fail(f"a split reply was not joined: {got!r}")


def test_text_of_survives_a_single_part_and_empty():
    if gemini_text.text_of({"candidates": [{"content": {"parts": [{"text": " ok "}]}}]}) != "ok":
        fail("a single part must be stripped and returned")
    if gemini_text.text_of({}) != "" or gemini_text.text_of({"candidates": []}) != "":
        fail("an empty reply must give an empty string, not raise")


def test_no_script_reads_only_the_first_part():
    bad = []
    for path in glob.glob(os.path.join(ROOT, "scripts", "*.py")):
        if os.path.basename(path).startswith("test_"):
            continue
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if RAW_READ.search(line):
                bad.append(f"{os.path.relpath(path, ROOT)}:{i}")
    if bad:
        fail("these read only the first Gemini part (tail can be lost): " + ", ".join(bad))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all gemini-text checks passed")
