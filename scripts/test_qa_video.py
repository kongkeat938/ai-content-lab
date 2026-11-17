#!/usr/bin/env python3
"""Guard the Q/A long-form renderer (the reference-look standard).

The owner's target (2026-11-17) is a Google Veo clip: a big Thai question, a Thai
answer caption at the bottom, and a realistic picture that is not a static card.
Veo is not available to us, so make_qa_video.py reproduces the FORMAT for free.
This test locks the properties that make the output match that format, and that a
regression must break:

  * the text overlay actually draws Thai pixels (a blank card must fail);
  * the caption sits at the BOTTOM and the question at the TOP-LEFT;
  * the render is 1280x720, yuv420p, tv colour range (verify_night's gate);
  * the answer caption is not drawn when a beat has no answer.

    python3 scripts/test_qa_video.py    # exit 0 = the standard holds

Needs ffmpeg + PIL. Renders a ~3 s fixture, so it finishes in well under a minute.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_qa_video as mq  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def bright_frac(png: str) -> tuple[float, float]:
    """Fraction of bright pixels in the top third and bottom third of a frame."""
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(png).convert("L")).astype("float32")
    h = a.shape[0]
    bright = a > 200
    return bright[: h // 3].mean(), bright[-h // 3:].mean()


def main() -> int:
    if not shutil.which("ffmpeg"):
        fail("ffmpeg not found")
    tmp = tempfile.mkdtemp(prefix="qa_guard_")

    from PIL import Image
    import numpy as np

    # 1. The overlay draws real Thai pixels, in the reference layout.
    card = os.path.join(tmp, "card.png")
    mq.text_card("ทำไมท้องฟ้า ถึงเป็นสีฟ้า?", "เพราะแสงแดดกระเจิงกับอากาศ", card)
    alpha = np.asarray(Image.open(card).convert("RGBA"))[..., 3]
    if alpha.max() == 0:
        fail("overlay is empty: PIL drew no text")
    h = alpha.shape[0]
    if alpha[: h // 3].sum() == 0:
        fail("question missing from the top of the overlay")
    if alpha[-h // 3:].sum() == 0:
        fail("answer caption missing from the bottom of the overlay")

    # 2. A beat with no answer must not draw a caption band.
    card2 = os.path.join(tmp, "card2.png")
    mq.text_card("คำถามอย่างเดียว?", "", card2)
    a2 = np.asarray(Image.open(card2).convert("RGBA"))[..., 3]
    if a2[-h // 3:].sum() != 0:
        fail("caption band drawn for a beat that has no answer")

    # 3. The render is 16:9, tv range, with a still under the text.
    img = os.path.join(tmp, "still.png")
    Image.new("RGB", (mq.W, mq.H), (30, 90, 170)).save(img)
    aud = os.path.join(tmp, "silence.m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=stereo", "-t", "3", aud], check=True)
    out = os.path.join(tmp, "seg.mp4")
    mq.scene_still(img, card, aud, out)
    info = mq.probe(out)
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), {})
    if (v.get("width"), v.get("height")) != (mq.W, mq.H):
        fail(f"render is {v.get('width')}x{v.get('height')}, not {mq.W}x{mq.H}")
    if v.get("color_range") != "tv":
        fail(f"colour range is {v.get('color_range')!r}, verify_night needs 'tv'")
    if not any(s["codec_type"] == "audio" for s in info.get("streams", [])):
        fail("render has no audio stream")

    # 4. The text is really burned into the video, top and bottom.
    png = os.path.join(tmp, "f.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", out,
                    "-frames:v", "1", png], check=True)
    top_f, bot_f = bright_frac(png)
    if top_f < 0.001:
        fail(f"no bright text pixels in the top third (got {top_f:.4f})")
    if bot_f < 0.001:
        fail(f"no bright caption pixels in the bottom third (got {bot_f:.4f})")

    # 4b. The card must survive to the END of the beat, not just the first frame.
    # The card is a single still fed to a fade filter, so without looping it the
    # fade blanks it after ~0.5 s and beats 2..N render textless (measured
    # 2026-11-17). Extract a late frame and require the text is still there.
    late = os.path.join(tmp, "late.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2.5", "-i", out,
                    "-frames:v", "1", late], check=True)
    ltop, lbot = bright_frac(late)
    if ltop < 0.001 or lbot < 0.001:
        fail(f"card vanished before the beat ended (late top={ltop:.4f} "
             f"bottom={lbot:.4f}); the card input must be looped")

    # 5. Loudness normalisation lands on the -14 LUFS YouTube target.
    quiet = os.path.join(tmp, "quiet.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=300:duration=5", "-af", "volume=-18dB",
                    "-c:a", "aac", quiet], check=True)
    before, _ = mq.measure_loud(quiet)
    mq.finalize(quiet)
    after, peak = mq.measure_loud(quiet)
    if abs(after - mq.LOUD_I) > 1.5:
        fail(f"finalize left {after:.1f} LUFS (target {mq.LOUD_I}); was {before:.1f}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: Q/A overlay, layout, 16:9 tv-range render, burned-in text and "
          "loudness normalisation all hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
