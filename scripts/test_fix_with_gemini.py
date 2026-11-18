#!/usr/bin/env python3
"""Guard the 'failed quality -> ask Gemini for a fix' path (no network calls).

K (2026-11-18): *"คุณภาพงานที่ไม่ผ่าน เอาไปถาม gemini เลย"*. `fix_with_gemini.fix()`
must, for a failed artifact, produce a prompt that carries the measured reasons and
hand back Gemini's fix. This test injects a fake `ask` so it never touches the
network, and it must be able to FAIL:

  * a prompt that drops the reasons (a fix blind to the failure) fails
  * a dead advisor must return ok=False, never raise into the gate
  * a reply that is not a usable script must not be reported as one

    python3 scripts/test_fix_with_gemini.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fix_with_gemini as fg  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def test_prompt_carries_every_reason():
    reasons = ["hook 41s, over the 30s ceiling", "longest card holds 9.0 min"]
    p = fg.build_prompt("shorts_script", {"id": "07", "hook": "x"}, reasons)
    for r in reasons:
        if r not in p:
            fail(f"the prompt dropped a measured reason: {r!r}")


def test_fix_returns_the_advisor_answer():
    reply = 'แก้แล้ว:\n{"hook": "ใหม่", "lines": ["a", "b"], "cta": "ติดตาม"}'
    r = fg.fix("shorts_script", {"id": "07"}, ["hook ยาว"], ask=lambda _p: reply)
    if not r["ok"] or r["fix_text"] != reply:
        fail(f"a live advisor answer was not returned: {r}")
    if r.get("script", {}).get("hook") != "ใหม่":
        fail(f"the usable script was not parsed out: {r.get('script')}")


def test_a_dead_advisor_is_recorded_not_raised():
    def boom(_p):
        raise RuntimeError("GEMINI_API_KEY not set")
    r = fg.fix("manifest_entry", {"key": "k"}, ["no hook"], ask=boom)
    if r["ok"] or "error" not in r:
        fail(f"a dead advisor must give ok=False + error, got {r}")


def test_an_unusable_reply_is_not_a_script():
    r = fg.fix("shorts_script", {"id": "1"}, ["x"], ask=lambda _p: "ไม่มี json ที่ใช้ได้")
    if not r["ok"]:
        fail("a non-empty reply is still ok=True (only the script is absent)")
    if r.get("script") is not None:
        fail(f"a reply with no script object must not invent one: {r.get('script')}")


def test_house_standard_is_in_the_prompt():
    p = fg.build_prompt("shorts_script", {}, ["x"])
    if "9:16" not in p or "-14 LUFS" not in p:
        fail("the prompt must carry the house standard so a fix cannot break it")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all fix-with-gemini checks passed")
