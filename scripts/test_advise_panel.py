#!/usr/bin/env python3
"""Guards the advisor-panel wiring in scripts/advise.py (no network calls).

Two rules are enforced here.

1. **K's current rule (2026-11-18): the panel is Gemini alone.** *"ทีมที่ปรึกษาให้
   ใช้ gemini คนเดียวพอ"* and *"ต้องทำตามคำสั่งและแนะนำของ gemini เมื่อติดปัญหา"*.
   The default panel and the light panel must each resolve to exactly one vendor
   (Gemini), not the old five voices across two vendors. If a default panel grows
   a second vendor, or loses Gemini, this fails -- so a stray edit cannot quietly
   undo K's rule.

2. **A panel name must be registered.** The panel once shipped a name
   (`gemini-latest`) that was missing from ADVISORS, so a slot silently degraded
   to "(unknown advisor)" while still counting as a panelist. That class of bug
   must fail loudly.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise  # noqa: E402

# Names served by the Gemini vendor (share GEMINI_API_KEY). Anything else in a
# default panel is a second vendor and breaks K's "Gemini alone" rule.
GEMINI_NAMES = {"gemini", "gemini-3.5", "gemini-3.1", "gemini-flash", "gemini-preview"}


def test_every_panel_name_exists():
    for group in ("FAST", "FAST_PLUS", "BROAD", "DEEP", "LIGHT"):
        names = getattr(advise, group, None)
        assert names is not None, f"advise.{group} is missing"
        missing = [n for n in names if n not in advise.ADVISORS]
        assert not missing, f"{group} references unknown advisors: {missing}"


def test_default_panel_is_gemini_alone():
    """K (2026-11-18): the panel is Gemini, one vendor. Not five voices."""
    team = advise.resolve_team(list(advise.FAST))
    assert len(team) == 1, f"K's rule is Gemini alone, not a panel of {team}"
    assert team[0] in GEMINI_NAMES, f"the one advisor must be Gemini, got {team}"


def test_light_panel_is_gemini_alone():
    """The loop's own panel. K (2026-11-18): Gemini alone, so a stuck decision is
    Gemini's to make and ak follows it."""
    light = getattr(advise, "LIGHT", None)
    assert light is not None, "advise.LIGHT is missing (the shared light panel)"
    assert len(light) == 1, light
    assert light[0] in GEMINI_NAMES, light


def test_no_default_panel_uses_a_second_vendor():
    """Sweep every default panel (a hardcoded group name is how a guard goes blind
    to a new group): each must be Gemini only, except the opt-in DEEP team."""
    for gname, names in vars(advise).items():
        if not (gname.isupper() and isinstance(names, list)) or gname == "DEEP":
            continue
        assert all(n in GEMINI_NAMES for n in names), \
            f"{gname} uses a second vendor: {names}"


def test_unknown_advisor_is_loud():
    """A name that is not registered is a wiring bug, so it must raise, not be
    skipped. `.get(name)` + `continue` is how the light panel lost its Google
    advisor silently for days."""
    try:
        advise.advisor("definitely-not-an-advisor")
    except KeyError:
        return
    raise AssertionError("advise.advisor() must raise KeyError on an unknown name")


def test_scripts_share_one_light_team():
    """The four scripts that ask the light panel must not hardcode the names:
    a literal tuple is how they drifted out of sync with the registry."""
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("studio_ai.py", "video_review.py", "diagnose_videos.py",
                 "panel_scorecard.py"):
        src = open(os.path.join(here, name), encoding="utf-8").read()
        assert '("gemini", "pollinations")' not in src, \
            f"{name} hardcodes the light panel; use advise.LIGHT"
        assert "advise.LIGHT" in src or "import LIGHT" in src or "LIGHT" in src, \
            f"{name} does not use the shared light team"


def test_no_dead_vendor_is_used():
    """K's rule (2026-11-15): 'ตัวไหนติดไม่ต้องใช้เลย' -- whichever advisor is
    blocked must not be used. openrouter measured DEAD (no key, every call raised
    'no OpenRouter key'), so it must be gone from the registry AND every panel.
    This SWEEPS the module for every panel list (a hardcoded group name is how a
    guard goes blind to a new group), so re-adding a dead vendor anywhere fails."""
    assert "openrouter" not in advise.ADVISORS, sorted(advise.ADVISORS)
    groups = {n: v for n, v in vars(advise).items()
              if n.isupper() and isinstance(v, list)}
    assert groups, "no panel groups found to sweep in advise.py"
    for gname, names in groups.items():
        assert "openrouter" not in names, f"{gname} still uses the dead openrouter: {names}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all advise-panel checks passed")

