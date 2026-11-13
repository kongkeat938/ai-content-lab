#!/usr/bin/env python3
"""Parse a YouTube ISO-8601 duration ("PT1H2M3S") into whole seconds, safely.

Measured 2026-11-13: ch4-realign died in `channel_overhaul.secs()` with
`AttributeError: 'NoneType' object has no attribute 'groups'`. YouTube returns
durations the old regex could not match -- `P0D` (a zero-length item, e.g. a
scheduled/processing upload), `P1DT2H` (a day component), and the empty string --
so `re.match` returned None and `.groups()` raised. The rail died at the step that
renames the playlists and sets the trailer, with no fallback.

The same fragile two-line parser had been copy-pasted into TEN scripts, so a fix
in one file would leave nine crashes. This module is the single place a duration is
parsed; every caller imports it. `scripts/test_duration_parse.py` sweeps the source
and fails if the fragile inline pattern returns to any script.
"""
from __future__ import annotations

import re

# Days are optional, hours/minutes/seconds are optional, and every component may
# be absent ("P0D" carries no value at all). Seconds may be fractional.
_ISO = re.compile(
    r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def seconds(iso: str | None) -> int:
    """Whole seconds for a YouTube ISO-8601 duration; 0 for anything unparseable.

    Never raises: a duration the regex cannot match is a fact worth 0, not a crash
    that takes down a rail.
    """
    m = _ISO.match(iso or "")
    if not m:
        return 0
    d, h, mi, s = m.groups()
    return (int(d or 0) * 86400 + int(h or 0) * 3600
            + int(mi or 0) * 60 + int(float(s or 0)))
