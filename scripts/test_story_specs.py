#!/usr/bin/env python3
"""A story spec that cannot be rendered, or that collides with a live title, FAILS.

K (2026-11-21) asked for new stories; the renderer (`standard_clip.py` /
`longform_clip.py`) reads only `narration`, `prompts`, `title`, `subtitle`, so a
typo there costs a whole render. This guard sweeps every `content/standard/*.json`
-- it never hardcodes the set -- and proves itself by feeding a deliberately
broken spec through the same checks.

    python3 scripts/test_story_specs.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPECS = os.path.join(ROOT, "content", "standard")
MIN_LINES, MAX_LINES = 120, 400
MAX_LINE_CHARS = 80
MIN_PROMPTS, MAX_PROMPTS = 8, 16
MAX_TITLE = 95
MAX_HOOK = 220


def _compilation_problems(spec: dict, titles: set[str], name: str) -> list[str]:
    """A compilation reads `parts_dir` + `topics`, not `narration`/`prompts`."""
    out = []
    for key in ("channel", "title", "subtitle", "parts_dir", "topics"):
        if not spec.get(key):
            out.append(f"{name}: missing '{key}'")
    if out:
        return out
    parts = sorted(glob.glob(os.path.join(ROOT, spec["parts_dir"], "*.txt")))
    if not parts:
        out.append(f"{name}: parts_dir {spec['parts_dir']} holds no .txt part")
    elif len(parts) != len(spec["topics"]):
        out.append(f"{name}: {len(parts)} part file(s) for {len(spec['topics'])} topics -- "
                   f"a dropped part must FAIL, never ship a partial set")
    for part in parts:
        text = open(part, encoding="utf-8").read()
        if not text.strip():
            out.append(f"{name}: {os.path.basename(part)} is empty")
        elif any(c.isascii() and c.isalpha() for c in text):
            out.append(f"{name}: Latin letters in {os.path.basename(part)}")
    if len(spec["title"]) > MAX_TITLE:
        out.append(f"{name}: title is {len(spec['title'])} chars (max {MAX_TITLE})")
    if spec["title"] in titles:
        out.append(f"{name}: title duplicates another live spec -- one live title, one video")
    titles.add(spec["title"])
    return out


def problems(spec: dict, titles: set[str], name: str) -> list[str]:
    if spec.get("parts_dir"):
        return _compilation_problems(spec, titles, name)
    out = []
    for key in ("channel", "title", "subtitle", "narration", "prompts"):
        if not spec.get(key):
            out.append(f"{name}: missing '{key}'")
    if out:
        return out
    nar = spec["narration"]
    if not isinstance(nar, list) or not all(isinstance(x, str) for x in nar):
        return [f"{name}: narration must be a list of strings"]
    story = spec.get("kind") == "story"
    if story and not MIN_LINES <= len(nar) <= MAX_LINES:
        out.append(f"{name}: story of {len(nar)} narration lines, expected {MIN_LINES}-{MAX_LINES}")
    long = [x for x in nar if len(x) > MAX_LINE_CHARS]
    if long:
        out.append(f"{name}: {len(long)} line(s) over {MAX_LINE_CHARS} chars, e.g. {long[0][:40]!r}")
    latin = [x for x in nar if any(c.isascii() and c.isalpha() for c in x)]
    if latin:
        out.append(f"{name}: Latin letters in the Thai narration, e.g. {latin[0]!r}")
    blank = [i for i, x in enumerate(nar) if not x.strip()]
    if blank:
        out.append(f"{name}: blank narration line(s) at {blank[:3]}")
    lo = MIN_PROMPTS if story else 1
    if not lo <= len(spec["prompts"]) <= MAX_PROMPTS:
        out.append(f"{name}: {len(spec['prompts'])} prompts, expected {lo}-{MAX_PROMPTS}")
    if len(spec["title"]) > MAX_TITLE:
        out.append(f"{name}: title is {len(spec['title'])} chars (max {MAX_TITLE})")
    if spec.get("hook") and len(spec["hook"]) > MAX_HOOK:
        out.append(f"{name}: hook is {len(spec['hook'])} chars (max {MAX_HOOK})")
    if spec["title"] in titles:
        out.append(f"{name}: title duplicates another live spec -- one live title, one video")
    titles.add(spec["title"])
    return out


def main() -> int:
    names = sorted(f for f in os.listdir(SPECS) if f.endswith(".json"))
    if not names:
        print(f"FAIL: no specs under {SPECS}")
        return 1
    titles: set[str] = set()
    bad: list[str] = []
    for name in names:
        with open(os.path.join(SPECS, name), encoding="utf-8") as fh:
            spec = json.load(fh)
        bad += problems(spec, titles, name)
    for b in bad:
        print(f"FAIL: {b}")
    if bad:
        return 1

    # The guard must be able to FAIL: the same checks, on a broken copy.
    broken = {"channel": "dharma", "kind": "story", "title": "x" * (MAX_TITLE + 5), "subtitle": "s",
              "narration": ["ok"] * 10 + ["มีคำอังกฤษ slipped in"] + ["ย" * (MAX_LINE_CHARS + 5)],
              "prompts": ["p"] * 3}
    caught = problems(broken, set(), "broken-copy")
    if len(caught) < 4:
        print(f"FAIL: the guard let a broken spec through ({caught})")
        return 1

    # The compilation branch must be able to FAIL: one topic with no part file.
    broken_comp = {"channel": "kongkeat", "title": "t", "subtitle": "s",
                   "parts_dir": "content/standard/kongkeat_long_01",
                   "topics": ["a", "b", "c"]}
    if not any("part file(s)" in c for c in problems(broken_comp, set(), "broken-comp")):
        print("FAIL: a compilation with a dropped part was not caught")
        return 1
    print(f"OK: {len(names)} spec(s) renderable, titles unique, and the guard rejects "
          f"{len(caught)} faults in a broken copy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
