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


def luma_of(src: str, vf: str) -> float:
    """Mean luma (0-255) of one frame of `src` after filter chain `vf`."""
    import subprocess
    import tempfile
    import os
    from PIL import Image
    import numpy as np
    p = os.path.join(tempfile.mkdtemp(prefix="luma_"), "f.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", src,
                    "-frames:v", "1", "-vf", vf, p], check=True)
    return float(np.asarray(Image.open(p).convert("L"), dtype=float).mean())


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
    # 1b. Floating text, not a dark box: the panel (2026-11-17) rejected the
    #     frosted-glass containers as 'PowerPoint / UI clutter'. The overlay must
    #     not lay down a large opaque panel behind the type -- sample the row the
    #     question sits on, away from the glyphs, and require it stays transparent.
    row = alpha[130]
    if (row > 200).mean() > 0.5:
        fail("the question row is mostly opaque: a dark box was drawn behind the "
             "text instead of floating type")

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

    # 6. A cached clip must be REUSED, not discarded. The old guard
    #    `elif broll and not os.path.exists(clip)` skipped the fetch and never
    #    set got_clip, so a rebuild silently fell back to a still (measured
    #    2026-11-17: run 2 rendered 3 of 4 beats as stills). Pre-seed the work
    #    dir with a clip and assert build() keeps it as the b-roll base.
    import json as _json
    bwork = os.path.join(tmp, "bw")
    os.makedirs(bwork, exist_ok=True)
    clip = os.path.join(bwork, "01_broll.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=green:s=640x360:d=4:r=30", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", clip], check=True)
    script = os.path.join(tmp, "s.json")
    _json.dump({"title": "ทดสอบ", "beats": [
        {"question": "คำถาม?", "answer": "คำตอบ", "broll": "blue sky"}]},
        open(script, "w", encoding="utf-8"))
    bout = os.path.join(tmp, "bout.mp4")
    mq.build(script, bout, bwork, "knowledge", mq.VOICE, mq.RATE, None,
             broll=True, brand="ทดสอบ")
    # The cached clip is green; a fallback still would be the blue-sky generator.
    frame = os.path.join(tmp, "bf.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", bout,
                    "-frames:v", "1", frame], check=True)
    arr = np.asarray(Image.open(frame).convert("RGB"), dtype=float)
    g, b = arr[..., 1].mean(), arr[..., 2].mean()
    if not (g > 40 and g > b + 30):
        fail(f"a cached b-roll clip was discarded (frame mean G={g:.0f} B={b:.0f}); "
             "build() fell back to a still instead of reusing the clip")

    # 7. The grade must stay CLEAN: no film grain, no vignette. The owner
    #    rejected the shipped cut as "ไม่คมชัด ขุ่นมัว" (not sharp, muddy); a
    #    vision grader scored the old `noise=alls=4` + `vignette=PI/4.5` grade
    #    2/10 ("smeared vaseline, digital noise, muddy vignette") and measured
    #    mean luma fall 171->123. A flat white frame run through GRADE must keep
    #    its brightness (a vignette darkens the corners) and add no grain.
    white = os.path.join(tmp, "white.png")
    Image.new("RGB", (mq.W, mq.H), (235, 235, 235)).save(white)
    graded = os.path.join(tmp, "graded.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", white,
                    "-vf", mq.GRADE, "-frames:v", "1", graded], check=True)
    ga = np.asarray(Image.open(graded).convert("L"), dtype=float)
    corner = np.concatenate([ga[:60, :60].ravel(), ga[:60, -60:].ravel(),
                             ga[-60:, :60].ravel(), ga[-60:, -60:].ravel()])
    center = ga[ga.shape[0] // 2 - 30: ga.shape[0] // 2 + 30,
                ga.shape[1] // 2 - 30: ga.shape[1] // 2 + 30]
    if center.mean() < 180:
        fail(f"grade darkens a white frame to {center.mean():.0f}; the picture "
             "reads muddy (brightness must survive the grade)")
    if corner.mean() < center.mean() - 12:
        fail(f"grade vignettes the corners ({corner.mean():.0f} vs centre "
             f"{center.mean():.0f}); the owner rejected a muddy vignette")
    # Grain = high-frequency variance on a FLAT frame. A clean grade (unsharp
    # only) leaves a flat field flat; `noise=` injects speckle.
    lap = (-4 * ga[1:-1, 1:-1] + ga[:-2, 1:-1] + ga[2:, 1:-1]
           + ga[1:-1, :-2] + ga[1:-1, 2:]).var()
    if lap > 50:
        fail(f"grade adds grain to a flat frame (LapVar={lap:.0f}); drop `noise=`")

    # 7b. The production rail's b-roll grade must be clean too (same defect).
    import make_kinetic_video as mkv
    for name, chain in (("BROLL_GRADE", mkv.BROLL_GRADE),):
        if "noise=" in chain or "vignette=" in chain:
            fail(f"{name} still carries grain/vignette: {chain!r}")

    # 8. The b-roll background must NOT soften the source. Measured 2026-11-17:
    #    the drift upscale cost sharpness (a 1.30x zoom keeps only ~39% of the
    #    frame detail), and a vision grader then called the cut "soft/compressed".
    #    Render a band-limited test frame (blurred, so it behaves like real
    #    footage, not a Nyquist pattern) native vs through broll_chain(), and
    #    require the chain keeps >= 65% of the native centre detail. This FAILS
    #    if someone raises BROLL_ZOOM toward 1.3 or drops the lanczos flag.
    clip = os.path.join(tmp, "detail.mp4")
    # The band limit follows the canvas: real footage carries detail up to its own
    # line count, not the output's, so a 4K frame must be blurred twice as wide as a
    # 1080p one to behave the same (measured 2026-11-24: sigma=2 on a 4K frame is a
    # near-Nyquist pattern, and the 6% zoom then read as a 39% detail loss).
    sigma = 2 * mq.H / 1080
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=s={mq.W}x{mq.H}:d=2:r={mq.FPS}", "-vf", f"gblur=sigma={sigma:g}",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", clip],
                   check=True)

    def centre_detail(src: str, vf: str) -> float:
        p = os.path.join(tmp, "d.png")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", src,
               "-frames:v", "1"]
        if vf:
            cmd += ["-vf", vf]
        subprocess.run(cmd + [p], check=True)
        g = np.asarray(Image.open(p).convert("L"), dtype=float)
        h, w = g.shape
        c = g[h // 2 - 150:h // 2 + 150, w // 2 - 150:w // 2 + 150]
        return (-4 * c[1:-1, 1:-1] + c[:-2, 1:-1] + c[2:, 1:-1]
                + c[1:-1, :-2] + c[1:-1, 2:]).var()

    native = centre_detail(clip, f"scale={mq.W}:{mq.H},crop={mq.W}:{mq.H},{mq.GRADE}")
    graded = centre_detail(clip, mq.broll_chain(clip).replace(",setsar=1", ""))
    if graded < native * 0.65:
        fail(f"b-roll chain softens the picture: centre LapVar {graded:.0f} vs "
             f"native {native:.0f} ({graded / native:.0%}); lower BROLL_ZOOM or "
             f"keep flags=lanczos")
    print(f"  #8 b-roll detail kept: {graded / native:.0%} of native "
          f"({graded:.0f}/{native:.0f})")

    # 9. A dark b-roll clip must be brightness-normalised, so no beat reads muddy
    #    next to a bright one (measured 2026-11-17: cat luma 107 vs sky 176). A
    #    synthetic dark clip must be lifted by broll_chain, a bright one left
    #    alone. FAILS if broll_gamma stops lifting or over-brightens.
    dark = os.path.join(tmp, "dark.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=s={mq.W}x{mq.H}:d=2:r={mq.FPS},eq=brightness=-0.45",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", dark],
                   check=True)
    raw = mq.fetch_broll.mean_luma(dark)
    if mq.broll_gamma(dark) <= 1.0:
        fail(f"dark clip (luma {raw:.0f}) got no brightness lift from broll_gamma")
    lifted = luma_of(dark, mq.broll_chain(dark).replace(",setsar=1", ""))
    if lifted < raw + 25:
        fail(f"dark clip barely lifted: {raw:.0f} -> {lifted:.0f}")
    bright = os.path.join(tmp, "bright.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=s={mq.W}x{mq.H}:d=2:r={mq.FPS},eq=brightness=0.35",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", bright],
                   check=True)
    if mq.broll_gamma(bright) != 1.0:
        fail("an already-bright clip was wrongly gamma-lifted (highlights will blow)")
    print(f"  #9 dark clip lifted {raw:.0f} -> {lifted:.0f}; bright clip untouched")

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: Q/A overlay, layout, 16:9 tv-range render, burned-in text, "
          "loudness normalisation and a clean (grain-free, unvignetted) grade hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
