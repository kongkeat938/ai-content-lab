#!/usr/bin/env python3
"""Guard the kinetic renderer against the failure it exists to prevent.

ch4's 5.2% AVD came from a still card. The one thing that must never regress is
"the picture moves on every frame", so this test FAILS if the background chain
loses every time-varying source, and FAILS if a caption can be laid out with no
fade/slide (a static caption is the same defect one layer down).

It also drives the caption builder on a synthetic timing so the sync maths
(end = next start, clamped to the file length) is exercised for real.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_kinetic_video as mk  # noqa: E402


def test_background_moves() -> None:
    src = mk.gradient_source(0, 30.0)
    chain = mk.background_chain(0)
    both = src + "," + chain
    assert "gradients" in src, f"gradient source lost its motion: {src!r}"
    assert any(tok in both for tok in mk.MOTION_TOKENS), (
        f"background has no motion source: {both!r} -- this is the static "
        "card that measured 5.2% AVD")


def test_captions_are_kinetic_and_synced() -> None:
    lines = [
        {"text": "บรรทัดแรก", "start": 0.5},
        {"text": "บรรทัดที่สอง", "start": 4.0},
        {"text": "บรรทัดสุดท้าย", "start": 9.0},
        {"text": "ไม่มีเวลา", "start": None},  # must be skipped, never mis-timed
    ]
    ass = mk.build_ass(lines, 14.0, "หัวข้อ", "แบรนด์")
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    # brand + title + 3 timed lines (the None line is dropped)
    assert len(dialogues) == 5, f"expected 5 dialogue lines, got {len(dialogues)}"
    # every caption line must carry a fade and a move (the kinetic entrance)
    caps = [d for d in dialogues if d.split(",")[3] == "Cap"]
    assert len(caps) == 3, f"expected 3 caption lines, got {len(caps)}"
    for d in caps:
        assert "\\fad(" in d and "\\move(" in d, f"static caption: {d!r}"
    # the untimed line must not appear at all
    assert "ไม่มีเวลา" not in ass, "an untimed line was laid out anyway"


def test_caption_end_clamped_to_total() -> None:
    ass = mk.build_ass([{"text": "เดียว", "start": 20.0}], 21.0, "", "")
    cap = [l for l in ass.splitlines() if l.startswith("Dialogue:") and ",Cap," in l][0]
    parts = cap.split(",")
    start, end = parts[1], parts[2]
    # end must not run past the 21 s file, and must be after the start
    assert mk._ts(21.0) >= end >= start, f"bad clamp: {start}..{end}"


def test_ts_format() -> None:
    assert mk._ts(0) == "0:00:00.00"
    assert mk._ts(3661.5) == "1:01:01.50"


def test_fonts_are_bundled() -> None:
    """libass must be pointed at the repo fonts, or Thai renders as garbage.

    Measured 2026-11-16: with no fontsdir, fontconfig on the runner had no Thai
    font and libass drew tofu ("แสงอาทิตย์" -> "บปพนฎิยแพพ"). The bundled Kanit
    must exist and be the directory the renderer passes to `subtitles`.
    """
    fonts = os.path.join(mk.ROOT, "assets", "fonts")
    assert os.path.isdir(fonts), f"bundled fonts dir missing: {fonts}"
    assert any(f.startswith("Kanit") for f in os.listdir(fonts)), \
        "Kanit is not bundled -- Thai captions would render as tofu"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("OK: kinetic renderer stays in motion and its captions stay synced")
