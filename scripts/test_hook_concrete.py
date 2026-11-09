#!/usr/bin/env python3
"""Guard the measured lever: the opening must be concrete, not abstract.

Measured 2026-11-09: dharma's 120-min long-form keeps only 28.9% of viewers at
the 2:00 mark (71% leave), while the channel's winning Shorts are all *specific
and actionable* ("นอนไม่หลับ? ลองทำท่านี้ 10 วินาที", "วางมือบนท้องนะ"). The old
long-form hook was abstract ("ไม่ต้องทำอะไรเลย") and matched nothing that works.

The decision (docs/DECISION-2026-11-09.md) therefore rewrote the dharma hook and
the night-set opening angle to open with a concrete action a listener can do at
once. This test fails if either drifts back to pure abstraction, so the fix cannot
be silently lost in a later edit.

    python3 scripts/test_hook_concrete.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A concrete action cue a listener can act on immediately. The proven winners
# use this shape; an abstract reassurance does not. Per channel: genx is
# philosophy (a calming action), kongkeat is family story (a concrete image).
CHANNEL_CUES = {
    "dharma.md": ("วางมือ", "หายใจเข้า", "หายใจออก", "ลองทำ", "ลองกด", "ปล่อยลมหายใจ"),
    "genx.md": ("วางมือ", "หายใจเข้า", "หายใจออก", "ลองทำ", "ปล่อยลมหายใจ"),
    "kongkeat.md": ("เรื่องของผู้ชาย", "มือที่คอยซ่อม", "กลับไปกอด"),
}

# The panel's other half of the lever: the promise must land fast. edge-tts Thai
# speaks ~9 characters per second here, so 220 characters is ~24 s -- inside the
# 30 s ceiling qa_gate enforces. Measured 2026-11-09: a 361-char hook spoke for
# 40.3 s, which both failed qa_gate (state=blocked) and matched the 28.9% retention
# at 2:00 -- a long opening is where the 71% who leave are lost.
MAX_HOOK_CHARS = 220


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    # Every channel's hook, not just dharma: measured 2026-11-09, genx was 279
    # chars (~31 s) -- over qa_gate's 30 s ceiling, so the next genx long-form
    # would have been vetoed before anyone noticed.
    for fname, cues in CHANNEL_CUES.items():
        hook_path = os.path.join(ROOT, "content", "hooks", fname)
        if not os.path.exists(hook_path):
            fail(f"missing {hook_path}")
        hook = open(hook_path, encoding="utf-8").read()
        if not any(c in hook for c in cues):
            fail(f"{fname} has no concrete cue (one of {cues}); the measured "
                 "lever is a concrete opening")
        chars = len(hook.strip())
        if chars > MAX_HOOK_CHARS:
            fail(f"{fname} is {chars} chars (~{chars/9:.0f}s spoken); it must be "
                 f"<= {MAX_HOOK_CHARS} so the promise lands before the 30 s "
                 "ceiling. A long opening is where retention is lost and qa_gate "
                 "blocks it.")

    gen = open(os.path.join(HERE, "gen_night_scripts.py"), encoding="utf-8").read()
    m = re.search(r'\(\s*"open"\s*,\s*"([^"]+)"', gen)
    if not m:
        fail("could not find the 'open' angle in gen_night_scripts.py ARC")
    open_angle = m.group(1)
    if not any(c in open_angle for c in ("ลงมือ", "วางมือ", "หายใจ", "ทำทันที")):
        fail("the night-set opening angle is abstract again; it must ask for a "
             f"concrete action. Got: {open_angle!r}")

    print("OK: every channel hook is concrete and short (the measured retention "
          "lever), and the night-set opening asks for a concrete action")
    return 0


if __name__ == "__main__":
    sys.exit(main())
