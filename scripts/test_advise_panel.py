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
    for group, names in (("FAST", advise.FAST), ("FAST_PLUS", advise.FAST_PLUS),
                         ("BROAD", advise.BROAD), ("DEEP", advise.DEEP)):
        missing = [n for n in names if n not in advise.ADVISORS]
        assert not missing, f"{group} references unknown advisors: {missing}"


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
