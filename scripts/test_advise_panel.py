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
                         ("DEEP", advise.DEEP)):
        missing = [n for n in names if n not in advise.ADVISORS]
        assert not missing, f"{group} references unknown advisors: {missing}"


def test_default_panel_has_at_least_five_independent_slots():
    assert len(advise.FAST_PLUS) >= 5, advise.FAST_PLUS
    assert len(set(advise.FAST_PLUS)) == len(advise.FAST_PLUS), "duplicate panelist"
    # more than one vendor: pollinations and openrouter are not Gemini.
    assert "pollinations" in advise.FAST_PLUS
    assert "openrouter" in advise.FAST_PLUS


def test_fast_is_a_subset_of_plus():
    assert set(advise.FAST) <= set(advise.FAST_PLUS)
    assert "openrouter" not in advise.FAST


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all advise-panel checks passed")
