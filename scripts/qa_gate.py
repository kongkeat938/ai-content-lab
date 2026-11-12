#!/usr/bin/env python3
"""The QA/critic gate: grade every finished build and veto the weak ones.

The advisor panel (2026-11-08, three camps: Google, OpenAI-OSS, OpenHands/DeepSeek)
was unanimous that the one missing role in this factory is a critic with the power
to *block* a release. Every other rail only checks that a file is well-formed --
loudness, true peak, length agreement -- which a boring video passes as easily as a
good one. So the factory shipped whatever it rendered, including the single static
card that held 5.2% average view duration.

This gate reads the build's own receipt and grades it A-D on the levers the panel
named. Grade C or D is a **veto**: the entry is written to the manifest as
`state=blocked`, and publish_batch refuses to upload a blocked entry. A blocked
build is not deleted; it waits for a human or a later re-render, and the reason is
recorded so the fix is obvious.

Hard gates (any failure caps the grade at D):
  * the verifier must have passed -- a malformed file is never publishable
  * a spoken hook must exist and be short (the panel's #1 retention lever)
  * the picture must change: at least two cards, and no card longer than
    MAX_CARD_SEC (the reused-content / static-card trap this rail exists to avoid)

Soft gates (affect the grade, do not veto on their own):
  * chapter cadence -- a picture change every few minutes is what the panel asked
  * length inside an intended band (15-40 min clip, or the 110-130 min sleep file)
    where a listener actually stays

    python3 scripts/qa_gate.py --receipt work/night/receipt.json
    python3 scripts/qa_gate.py --receipt work/night/receipt.json --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# A card that holds longer than this is the static-image trap. The panel's guidance
# was a picture change every 3-5 minutes; 8 minutes leaves headroom for a sleep file
# that groups pieces, while still failing the old one-card-for-120-minutes shape.
MAX_CARD_SEC = 8 * 60
# The spoken promise must land inside this window -- long enough to be a sentence,
# short enough that the viewer is still there when it ends.
HOOK_MIN_SEC, HOOK_MAX_SEC = 2.0, 30.0
# The two formats this operation ships on purpose, both "where a listener stays":
# the 15-40 min talk/teaching clip and the 110-130 min sleep file (build_night.py
# --minutes 120 -- that long file IS the format, not a defect). A length inside
# either band is full marks; outside both is a warning, never a veto.
LEN_OK_BANDS = ((15 * 60, 40 * 60), (110 * 60, 130 * 60))
# The night rail deliberately ships a 120-minute sleep file (build_night.py
# --minutes 120) -- that IS the format, not a defect. The old ceiling of 90 min
# vetoed every such build (measured 2026-11-09: a verified 120.5-min file was
# written state=blocked), so the ceiling now covers the intended 2-hour format
# with headroom while still failing a file that is nothing like the format.
LEN_WARN_MIN, LEN_WARN_MAX = 8 * 60, 150 * 60


def _get(d: dict, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def grade(receipt: dict) -> dict:
    """Return {grade, blocked, reasons, warnings, metrics}. Pure, so it is testable."""
    reasons: list[str] = []
    warnings: list[str] = []

    verdict = receipt.get("verdict")
    audio = receipt.get("audio_info") or {}
    video = receipt.get("video_info") or {}

    duration = float(video.get("duration_sec") or audio.get("duration_sec") or 0.0)
    chapters = int(video.get("chapters") or 0)
    cards = [float(x) for x in (video.get("chapter_seconds") or [])]
    hook = _get(audio, "hook", "duration_sec")
    tp = video.get("true_peak_dbfs")

    # --- hard gates ---------------------------------------------------------
    if verdict != "pass":
        reasons.append(f"verifier verdict is {verdict!r}, not 'pass'")

    if hook is None:
        reasons.append("no spoken hook: the first thing a viewer hears must be the "
                       "promise, not the body")
    elif not (HOOK_MIN_SEC <= float(hook) <= HOOK_MAX_SEC):
        reasons.append(f"hook is {float(hook):.1f}s, outside "
                       f"{HOOK_MIN_SEC:.0f}-{HOOK_MAX_SEC:.0f}s")

    if chapters < 2:
        reasons.append(f"{chapters} card(s): the picture must change during the file "
                       "(a single static card is the reused-content trap)")
    elif cards and max(cards) > MAX_CARD_SEC:
        worst = max(cards)
        reasons.append(f"longest card holds {worst/60:.1f} min, over the "
                       f"{MAX_CARD_SEC/60:.0f} min limit: the screen goes static")

    if tp is not None and float(tp) > -3.0:
        reasons.append(f"true peak {tp} dBFS above the -3 dBFS ceiling")

    # --- soft gates ---------------------------------------------------------
    if duration:
        if not any(lo <= duration <= hi for lo, hi in LEN_OK_BANDS):
            bands = " or ".join(f"{lo//60}-{hi//60} min" for lo, hi in LEN_OK_BANDS)
            warnings.append(f"length {duration/60:.1f} min is outside the "
                            f"{bands} bands where a listener stays")
        if not (LEN_WARN_MIN <= duration <= LEN_WARN_MAX):
            reasons.append(f"length {duration/60:.1f} min is far from any usable format")

    if cards and duration:
        avg = duration / len(cards)
        if avg > 5 * 60:
            warnings.append(f"a picture changes only every {avg/60:.1f} min on average")

    blocked = bool(reasons)
    if blocked:
        g = "D"
    elif warnings:
        g = "B"
    else:
        g = "A"

    return {
        "grade": g,
        "blocked": blocked,
        "reasons": reasons,
        "warnings": warnings,
        "metrics": {
            "duration_min": round(duration / 60, 1) if duration else None,
            "chapters": chapters,
            "longest_card_min": round(max(cards) / 60, 1) if cards else None,
            "hook_sec": round(float(hook), 1) if hook is not None else None,
            "true_peak_dbfs": tp,
        },
    }


def load(path: str) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    receipt = load(a.receipt)
    if not receipt:
        print(f"no receipt at {a.receipt}; cannot grade", file=sys.stderr)
        return 2

    r = grade(receipt)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        m = r["metrics"]
        print(f"QA grade {r['grade']}"
              f"  ({m['duration_min']} min, {m['chapters']} cards, "
              f"longest {m['longest_card_min']} min, hook {m['hook_sec']}s, "
              f"TP {m['true_peak_dbfs']} dBFS)")
        for x in r["reasons"]:
            print(f"  VETO: {x}")
        for x in r["warnings"]:
            print(f"  warn: {x}")
        if not r["blocked"]:
            print("  -> publishable")
    return 1 if r["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
