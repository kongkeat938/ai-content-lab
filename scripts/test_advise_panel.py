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
    # more than one vendor: openrouter is not Google.
    assert "openrouter" in advise.FAST


def test_default_team_excludes_the_measured_slow_advisor():
    # pollinations measured ~66 s vs ~0.5-1.5 s for the rest (panel_bench.py):
    # a slow panelist drags every decision, so it stays opt-in via --broad.
    assert "pollinations" not in advise.FAST
    assert "pollinations" in advise.BROAD
    assert set(advise.FAST) <= set(advise.BROAD)


def test_broad_is_default_plus_pollinations():
    assert advise.BROAD == advise.FAST + ["pollinations"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all advise-panel checks passed")
