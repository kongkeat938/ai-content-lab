#!/usr/bin/env python3
"""The gate a Shorts draft must pass before it may join the pool.

K (2026-11-28): the advisor/writer panel is gone -- ak decides alone. What
survives from the writing room is the part that was never an opinion: the
mechanical gate. A draft is usable only when it parses as the Shorts shape,
speaks for 35-45 s, carries no bare digit (edge-tts reads a digit wrong), no
emoji, no mixed-script gibberish, and its hook and story are not near-copies of
one already published. Everything else comes back with the reason it was
dropped.

    python3 scripts/shorts_draft_gate.py --check draft.json
    python3 scripts/shorts_draft_gate.py --check content/ch2_shorts/scripts.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

MIN_CHARS, MAX_CHARS = 250, 700      # ~35-45 s of Thai narration
HOOK_HARD = 95                       # the real cap: the title is hook[:95] + " #Shorts"
NOVEL_FLOOR = 8                      # Thai runs are short; 3 chars matched everything


def parse(text: str) -> dict | None:
    """Pull the JSON object out of a reply that may be fenced or chatty."""
    if not text or text.startswith("ERROR"):
        return None
    body = re.sub(r"```(?:json)?", "", text).strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        got = json.loads(body[start:end + 1])
    except json.JSONDecodeError:
        return None
    return got if isinstance(got, dict) else None


def problems(script: dict | None, existing_hooks: list[str] | None = None,
             existing_scripts: list[str] | None = None) -> list[str]:
    """Every reason this draft cannot be used. An empty list means it ships."""
    if not script:
        return ["not JSON"]
    out: list[str] = []
    hook = str(script.get("hook", "")).strip()
    lines = script.get("lines")
    cta = str(script.get("cta", "")).strip()
    if not hook:
        out.append("no hook")
    elif len(hook) > HOOK_HARD:
        out.append(f"hook {len(hook)} chars > {HOOK_HARD} (title truncates)")
    if not isinstance(lines, list) or not 5 <= len(lines) <= 10:
        out.append(f"lines must be a list of 5-10 (got "
                   f"{len(lines) if isinstance(lines, list) else type(lines).__name__})")
        lines = lines if isinstance(lines, list) else []
    if not cta:
        out.append("no cta")
    speech = hook + "".join(str(x) for x in lines) + cta
    if not MIN_CHARS <= len(speech) <= MAX_CHARS:
        out.append(f"speech {len(speech)} chars outside {MIN_CHARS}-{MAX_CHARS}")
    if re.search(r"[0-9]", speech):
        out.append("bare digit (edge-tts reads it wrong)")
    if re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", speech):
        out.append("emoji")
    stray = set(re.findall(r"[A-Za-z\u0400-\u04FF\u0E80-\u0EFF\u4E00-\u9FFF]", speech))
    if stray:
        out.append(f"non-Thai letters {''.join(sorted(stray))[:12]} (mixed-script gibberish)")
    for hook_seen in existing_hooks or []:
        if len(hook_seen) >= NOVEL_FLOOR and hook[:NOVEL_FLOOR] == hook_seen[:NOVEL_FLOOR]:
            out.append("hook repeats a published one")
            break
    # A different hook is not enough -- K (2026-11-23) wants the story itself new.
    if existing_scripts and speech:
        import upload_gate
        for share, other in ((upload_gate.similarity(speech, o), o) for o in existing_scripts):
            if share >= upload_gate.DUP_THRESHOLD:
                out.append(f"script is {share:.0%} the same as a published one "
                           f"({other[:24]}...)")
                break
    return out


def _items(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    data = json.load(open(path, encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("scripts", [])
    return [s for s in items if isinstance(s, dict)]


def existing_hooks(path: str) -> list[str]:
    return [str(s.get("hook", "")) for s in _items(path)]


def existing_texts(path: str) -> list[str]:
    """The words of every script already out, for the whole-story check."""
    return [str(s.get("hook", "")) + "".join(map(str, s.get("lines", []))) + str(s.get("cta", ""))
            for s in _items(path)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", required=True, help="a draft JSON (one object) or a pool file")
    ap.add_argument("--seen", default=None, help="pool whose hooks/scripts count as published")
    a = ap.parse_args()
    seen = existing_hooks(a.seen) if a.seen else []
    heard = existing_texts(a.seen) if a.seen else []
    items = _items(a.check)
    if not items:
        print(f"nothing to check in {a.check}")
        return 2
    bad = 0
    for s in items:
        got = problems(s, seen, heard)
        print(f"{s.get('id', '?')}: {'USABLE' if not got else '; '.join(got)}")
        bad += bool(got)
    print(f"\n{len(items) - bad}/{len(items)} usable")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
