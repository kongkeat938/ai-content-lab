#!/usr/bin/env python3
"""Guards the advisor panel wiring in scripts/advise.py (no network calls).

The panel once shipped a name (`gemini-latest`) that was missing from ADVISORS,
so a slot silently degraded to "(unknown advisor)" while still counting as a
panelist. These checks make that class of bug fail loudly.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise  # noqa: E402


def test_every_panel_name_exists():
    for group in ("FAST", "FAST_PLUS", "BROAD", "DEEP", "LIGHT"):
        names = getattr(advise, group, None)
        assert names is not None, f"advise.{group} is missing"
        missing = [n for n in names if n not in advise.ADVISORS]
        assert not missing, f"{group} references unknown advisors: {missing}"


def test_light_panel_is_real_and_two_vendors():
    """The loop's own panel. Measured 2026-11-11: the scripts asked for "gemini",
    which was not a registry key, so every one skipped it and the "panel" was
    pollinations alone -- or empty when pollinations 400'd. It must name only
    registered advisors and keep more than one vendor."""
    light = getattr(advise, "LIGHT", None)
    assert light is not None, "advise.LIGHT is missing (the shared light panel)"
    assert len(light) >= 2, light
    assert all(n in advise.ADVISORS for n in light), light
    assert "gemini" in light and "pollinations" in light, light


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


def test_default_team_has_at_least_five_independent_slots():
    assert len(advise.FAST) >= 5, advise.FAST
    assert len(set(advise.FAST)) == len(advise.FAST), "duplicate panelist"


def test_default_team_spans_two_vendors():
    # more than one vendor: pollinations is not Google.
    assert "pollinations" in advise.FAST, advise.FAST


def test_no_dead_vendor_is_used():
    """K's rule (2026-11-15): 'ตัวไหนติดไม่ต้องใช้เลย' -- whichever advisor is
    blocked must not be used at all. openrouter measured DEAD (no key, every call
    raised 'no OpenRouter key'), so it must be gone from the registry AND from every
    panel group. This SWEEPS the module for every panel list (a hardcoded group name
    is how a guard goes blind to a new group), so re-adding a dead vendor anywhere
    fails here."""
    assert "openrouter" not in advise.ADVISORS, sorted(advise.ADVISORS)
    groups = {n: v for n, v in vars(advise).items()
              if n.isupper() and isinstance(v, list)}
    assert groups, "no panel groups found to sweep in advise.py"
    for gname, names in groups.items():
        assert "openrouter" not in names, f"{gname} still uses the dead openrouter: {names}"


def test_default_panel_yields_five_real_voices():
    """The default team must resolve to >=5 registered voices across >=2 vendors."""
    team = advise.resolve_team(list(advise.FAST))
    assert len(team) >= 5, f"panel lost a voice: {team}"
    assert len(set(team)) == len(team), f"duplicate panelist: {team}"
    assert all(n in advise.ADVISORS for n in team), team
    assert "pollinations" in team, team


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all advise-panel checks passed")
