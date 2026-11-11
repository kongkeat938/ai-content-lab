#!/usr/bin/env python3
"""Guards for channel branding.

Measured 2026-11-11: every channel read defaultLanguage='en' with no
description, because channel_overhaul.set_trailer PUT brandingSettings.channel
with ONLY the trailer -- a PUT replaces the whole object, so it wiped what
set_channel_name had written, and set_channel_name then skipped on the title
alone. These guards must be able to FAIL.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERHAUL = (ROOT / "scripts" / "channel_overhaul.py").read_text(encoding="utf-8")
SETNAME = (ROOT / "scripts" / "set_channel_name.py").read_text(encoding="utf-8")
WF = ROOT / ".github" / "workflows" / "channel-branding.yml"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def set_trailer_body() -> str:
    m = re.search(r"def set_trailer\(.*?\n(?=class |\ndef )", OVERHAUL, re.S)
    if not m:
        fail("could not find set_trailer in channel_overhaul.py")
    return m.group(0)


def main() -> int:
    body = set_trailer_body()
    # A PUT replaces the whole object, so the writer must read the live
    # brandingSettings and echo it back; writing a literal object wipes the rest.
    if "part=brandingSettings&mine=true" not in body:
        fail("set_trailer does not read the live brandingSettings before its PUT; "
             "a PUT would wipe description/keywords/defaultLanguage")
    if "unsubscribedTrailer" not in body:
        fail("set_trailer no longer sets the trailer")
    # It must build the body from the live object, not a fresh literal dict.
    if not re.search(r"brandingSettings.*channel.*\n?.*=.*dict\(|ch\s*=\s*dict\(", body):
        fail("set_trailer does not copy the live channel object into its PUT body")

    # Every channel must have a branding target, with all three fields.
    for slug in ("genx", "dharma", "kongkeat-story"):
        m = re.search(rf'"{re.escape(slug)}":\s*\{{(.*?)\n    \}}', SETNAME, re.S)
        if not m:
            fail(f"set_channel_name has no TARGET for {slug}")
        blk = m.group(1)
        for field in ("description", "keywords", "lang"):
            if f'"{field}"' not in blk:
                fail(f"TARGET[{slug}] has no {field}")

    # The skip must require the branding, so a wiped channel is repaired.
    if not re.search(r'loc_th == t\["title"\] and default_lang == t\["lang"\]', SETNAME):
        fail("set_channel_name still skips on the title alone; a wiped channel "
             "would never be repaired")

    if not WF.exists():
        fail("no channel-branding.yml; branding is not applied to all channels")
    wf = WF.read_text(encoding="utf-8")
    for slug in ("genx", "dharma", "kongkeat-story"):
        if slug not in wf:
            fail(f"channel-branding.yml does not apply branding to {slug}")

    print("OK: the trailer merges branding, all channels have a target, and a "
          "wiped channel is repaired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
