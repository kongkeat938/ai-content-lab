#!/usr/bin/env python3
"""Guard the one number the tracker must not inflate: YPP-qualifying watch time.

progress.py compares a 28-day window against YPP's 4,000-hour bar. But the bar
counts **long-form only** -- Shorts have a separate path (10M views / 90 days)
and their watch time does not count. The channel-level total mixes both, so a
Shorts-heavy channel looked far closer to YPP than it was. Measured 2026-11-09:
genx's total said 39% of the bar; the long-form number was 0.4%, a 92x overstatement.

This pins the honesty of the tracker, offline:
  * progress.py must prefer `longform_watch_hours` from a sample and must NOT
    silently use the mixed total when that field is present;
  * a pre-split sample (no longform field) must be flagged, not passed off as exact;
  * analytics.py must expose the split so the field exists at all.

    python3 scripts/test_progress_honesty.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    import progress

    analytics_src = open(os.path.join(HERE, "analytics.py"), encoding="utf-8").read()
    for needle in ("content_type_hours", "longform_watch_hours", "videoOnDemand"):
        if needle not in analytics_src:
            fail(f"analytics.py does not expose the long-form split (missing {needle})")

    # A sample that carries the split: the tracker must use the long-form number,
    # not the mixed total, and must mark it exact.
    split_sample = {
        "measured_at": "2026-11-09T00:00:00+00:00", "days": 28,
        "channels": {
            "genx": {"views": 27014, "watch_hours": 120.2, "longform_watch_hours": 1.3,
                     "shorts_watch_hours": 118.9},
            "dharma": {"views": 14017, "watch_hours": 79.8, "longform_watch_hours": 44.4,
                       "shorts_watch_hours": 35.4},
            "kongkeat": {"views": 6126, "watch_hours": 19.9, "longform_watch_hours": 0.5,
                         "shorts_watch_hours": 19.4},
        },
    }
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "docs"))
        with open(os.path.join(td, "docs", "watch_hours.json"), "w") as fh:
            json.dump({"samples": [split_sample]}, fh)
        old_root = progress.ROOT
        progress.ROOT = td
        try:
            d = progress.build()
            rows = {r["slug"]: r for r in d["rows"]}
            if abs(rows["genx"]["hours"] - 1.3) > 1e-6:
                fail(f"genx hours={rows['genx']['hours']}, expected the long-form 1.3, "
                     f"not the mixed 120.2")
            if not rows["genx"]["lf_exact"]:
                fail("genx should be marked exact when longform_watch_hours is present")
            if abs(d["total"]["hours"] - (1.3 + 44.4 + 0.5)) > 1e-6:
                fail(f"total={d['total']['hours']}, expected the long-form sum 46.2")
            text = progress.render(d)
            if "long-form" not in text:
                fail("the report does not say the number is long-form only")

            # A pre-split sample: no longform field -> fall back to the total but
            # flag it, so a stale sample cannot masquerade as the exact number.
            stale = {"measured_at": "2026-11-08T00:00:00+00:00", "days": 28,
                     "channels": {"genx": {"views": 1, "watch_hours": 99.0},
                                  "dharma": {"views": 1, "watch_hours": 1.0},
                                  "kongkeat": {"views": 1, "watch_hours": 1.0}}}
            with open(os.path.join(td, "docs", "watch_hours.json"), "w") as fh:
                json.dump({"samples": [stale]}, fh)
            d2 = progress.build()
            r2 = {r["slug"]: r for r in d2["rows"]}["genx"]
            if r2["lf_exact"]:
                fail("a sample without longform_watch_hours must not be marked exact")
            if "รวม Shorts" not in progress.render(d2):
                fail("a stale sample must be flagged in the report, not passed off as exact")
        finally:
            progress.ROOT = old_root

    print("OK: the tracker reports long-form-only watch hours, flags pre-split samples, "
          "and analytics.py exposes the split")
    return 0


if __name__ == "__main__":
    sys.exit(main())
