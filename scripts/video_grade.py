#!/usr/bin/env python3
"""The ONE b-roll grade chain every renderer must use (single source of truth).

Measured 2026-11-17: the ch4 rail shipped `make_kinetic_video.py` while the
owner-approved look lived in `make_qa_video.py`, and the two had drifted apart --
on the SAME real clip the rail's chain scored **LapVar 15.4** against the approved
chain's **46.6** (~3x softer). The rail was missing `cas=0.6`, used bicubic
resampling instead of lanczos, zoomed 1.08 instead of 1.06, skipped the per-clip
brightness normalisation, and ran 25 fps instead of 30. So the live rail did NOT
ship the look the owner approved.

A five-advisor panel (2026-11-17, scripts/advise.py) was unanimous: do not
copy-paste the chain into both files (it drifts again the day one is tuned);
extract it here and let both import it, with a guard that fails on drift.

The look itself (from the approved make_qa_video.py):
  * `BROLL_ZOOM 1.06` + `lanczos` -- a small, sharp reframe; 1.08 bicubic blurred.
  * `unsharp` + `cas=0.6` -- local contrast, the sharpness the owner asked for.
  * per-clip gamma toward `BROLL_LUMA_TARGET` -- a dark clip next to a bright one
    reads as "ขุ่นมัว"; measured and lifted, capped so highlights hold.
"""
from __future__ import annotations

# K (2026-11-23): 4K only to upload. Every rail that builds a clip inherits this.
W, H, FPS = 3840, 2160, 30
BROLL_ZOOM = 1.06
BROLL_FLAGS = "lanczos"
# colorbalance warmth + contrast/saturation + unsharp + cas (local contrast).
GRADE = ("colorbalance=rs=0.03:gs=0.01:bs=-0.03,"
         "eq=contrast=1.08:saturation=1.14:brightness=0.025,"
         "unsharp=5:5:0.6:3:3:0.0,cas=0.6")
BROLL_LUMA_TARGET = 150.0
BROLL_GAMMA_MAX = 1.55


def broll_gamma(mean_luma: float) -> float:
    """Gamma to lift a clip toward BROLL_LUMA_TARGET, capped. Measured, not fixed."""
    if mean_luma >= BROLL_LUMA_TARGET:
        return 1.0
    g = 1.0 + (BROLL_LUMA_TARGET - mean_luma) / 120.0
    return round(min(g, BROLL_GAMMA_MAX), 3)


def broll_chain(mean_luma: float, *, w: int = W, h: int = H, fps: int = FPS,
                zoom: float = BROLL_ZOOM, flags: str = BROLL_FLAGS,
                grade: str = GRADE) -> str:
    """Fit a clip to 16:9, small lanczos zoom + drift, normalise, grade."""
    zx, zy = int(w * zoom), int(h * zoom)
    dx, dy = int(w * (zoom - 1) / 2), int(h * (zoom - 1) / 2)
    g = broll_gamma(mean_luma)
    norm = "" if g == 1.0 else f"eq=gamma={g},"
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags={flags},"
            f"crop={w}:{h},scale={zx}:{zy}:flags={flags},"
            f"crop={w}:{h}:x='{dx}+{dx}*sin(2*PI*t/23)':"
            f"y='{dy}+{dy}*cos(2*PI*t/29)',fps={fps},{norm}{grade},setsar=1")
