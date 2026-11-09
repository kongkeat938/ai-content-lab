#!/usr/bin/env python3
"""Guard the night-set generator: a failed piece must not ship a partial set.

Measured 2026-11-09: a scheduled run generated `content/night_auto_202646`
**without its `01_open`** -- one response tripped the shape gate and the piece was
skipped with only a log line. `build_night.py` globs whatever `.txt` it finds, so
the set built a shorter talk than the arc intends and, under the `--minutes`
floor, would be looped twice (the known duplicate-content bug). The opening is the
exact lever docs/DECISION-2026-11-09.md names, so a silent drop disarms the fix.

This test fails if the generator ever writes a partial set again.

    python3 scripts/test_night_scripts.py
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_night_scripts as G  # noqa: E402

FAILS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        FAILS.append(name)


GOOD = "\n".join(["หายใจเข้าลึก ๆ แล้วปล่อยออกช้า ๆ"] * 14)   # 14 lines, Thai, no digits


def main() -> int:
    # The arc must open the set with the concrete-action 'open' stage.
    check("ARC starts with 'open'", G.ARC[0][0] == "open", str(G.ARC[0][0]))

    ok, _ = G.valid(GOOD)
    check("valid() accepts a normal Thai block", ok)
    bad_digit = "\n".join(f"บรรทัด {i}" for i in range(14))
    check("valid() rejects digits", not G.valid(bad_digit)[0])

    # The decisive case: the 'open' stage keeps failing -> no partial set is written.
    def fake_ask(key: str, prompt: str) -> str:
        # The open prompt is the only one that mentions the concrete-action cue.
        if "วางมือ" in prompt or "ลงมือ" in prompt:
            return bad_digit        # never passes the gate
        return GOOD

    orig_ask, orig_env = G.ask, os.environ.get("GEMINI_API_KEY")
    G.ask = fake_ask
    os.environ["GEMINI_API_KEY"] = "test-key"
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "night_X")
        argv = sys.argv
        sys.argv = ["gen_night_scripts.py", "--theme", "ทดสอบ", "--out", out]
        raised = False
        try:
            G.main()
        except SystemExit as exc:
            raised = "partial" in str(exc) or "could not generate" in str(exc)
        finally:
            sys.argv = argv
            G.ask = orig_ask
            if orig_env is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = orig_env
        check("a failed piece aborts instead of writing a partial set", raised)
        wrote = os.path.isdir(out) and bool(os.listdir(out))
        check("no partial set was written to disk", not wrote)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: the night-set generator refuses to ship a set missing a piece")
    return 0


if __name__ == "__main__":
    sys.exit(main())
