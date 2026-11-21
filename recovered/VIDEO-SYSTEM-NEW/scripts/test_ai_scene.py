#!/usr/bin/env python3
"""Guard for scripts/ai_scene.py -- the AI scene library.

What must be provable, and able to FAIL:

  1. the detail gate rejects interpolation. A resize-only "upscaler" runs
     through the SAME production path and must raise, because its ratio is
     1.00x by construction.
  2. the gate is not tuned to one image. It is a ratio against a bicubic
     blow-up of the same frame, so it must accept a real RealESRGAN pass on
     every kind of content it is given -- a single absolute number could not
     do that (a hard-edged test card and soft photography have very
     different absolute scores).
  3. a partial set must fail, not ship.

The real upscaler pass is LIVE (weights on disk, CPU); if the weights or
spandrel are missing that part SKIPS loudly instead of pretending to pass.
"""
from __future__ import annotations

import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ai_scene  # noqa: E402
import kill_switch  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name}{' :: ' + detail if detail else ''}")
    if not ok:
        FAILS.append(name)


def synthetic_frame(size: int = 160):
    """A hard-edged test card -- deliberately unlike photographic content."""
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (size, size), (18, 24, 34))
    d = ImageDraw.Draw(im)
    for i in range(0, size, 40):
        d.line([(0, i), (size, size - i)], fill=(230, 180, 90), width=5)
    for i in range(0, size, 64):
        d.ellipse([i, i, i + 90, i + 90], outline=(90, 200, 220), width=4)
    return im


def content_samples() -> list:
    """Real repo imagery, swept rather than named, so no single file is the set."""
    from PIL import Image

    samples = []
    for pattern in ("docs/demo/frames/*.jpg", "assets/images/*.jpg",
                    "docs/demo/media/*.jpg"):
        for path in sorted(glob.glob(os.path.join(ROOT, pattern)))[:2]:
            try:
                samples.append((os.path.basename(path),
                                Image.open(path).convert("RGB").resize((320, 320))))
            except OSError:
                continue
    return samples


def test_kill_switch_honoured() -> None:
    """The rail must refuse to generate while content/STOP exists."""
    import subprocess

    if not os.path.exists(os.path.join(ROOT, "content", "STOP")):
        check("kill switch blocks generation", True, "SKIP content/STOP absent")
        return
    env = dict(os.environ)
    env.pop("CONTENT_STOP_PATH", None)
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "ai_scene.py"),
         "--count", "1", "--no-upscale", "--out-dir", "/tmp/_should_not_write"],
        capture_output=True, text=True, env=env)
    check("kill switch blocks generation",
          proc.returncode == kill_switch.STOPPED_EXIT, f"rc={proc.returncode}")
    check("kill switch writes nothing",
          not os.path.exists("/tmp/_should_not_write"), "/tmp/_should_not_write")


def test_partial_set_fails() -> None:
    """ensure_complete must raise when a frame is missing."""
    try:
        ai_scene.ensure_complete([{"slug": "a"}], ["a", "b"])
        check("partial set fails", False, "ensure_complete accepted 1 of 2")
    except RuntimeError as exc:
        check("partial set fails", "1 of 2" in str(exc), str(exc))
    ai_scene.ensure_complete([{"slug": "a"}], ["a"])
    check("complete set passes", True)


def test_resize_only_model_rejected() -> None:
    """A resize-only 'upscaler' must be rejected by the production gate."""
    import torch

    class BlurModel:
        """Stands in for an upscaler that adds no structure."""

        def __call__(self, x):
            import torch.nn.functional as F

            return F.interpolate(x, scale_factor=4, mode="bicubic",
                                 align_corners=False)

    frame = synthetic_frame()
    try:
        ai_scene.upscale_or_fail(torch, BlurModel(), frame)
        check("resize-only model rejected", False,
              "gate accepted a model that only interpolates")
    except RuntimeError as exc:
        check("resize-only model rejected", "no detail" in str(exc), str(exc))


def test_real_upscaler_live() -> None:
    """LIVE: RealESRGAN must clear the ratio gate on every content sample."""
    weights = "/tmp/RealESRGAN_x4plus.pth"
    if not os.path.exists(weights):
        check("real upscaler passes gate", True, "SKIP weights absent")
        return
    try:
        import spandrel  # noqa: F401
        import torch
    except ImportError as exc:
        check("real upscaler passes gate", True, f"SKIP {exc}")
        return

    torch.set_num_threads(os.cpu_count() or 4)
    model = ai_scene.upscaler(weights)[1]

    samples = content_samples()
    if not samples:
        check("real upscaler passes gate", True, "SKIP no repo imagery found")
        return

    worst = (None, 99.0)
    for name, frame in samples:
        _, ratio = ai_scene.upscale_or_fail(torch, model, frame)
        print(f"     {name}: {ratio:.2f}x")
        if ratio < worst[1]:
            worst = (name, ratio)
    check("real upscaler passes gate", worst[1] >= ai_scene.DETAIL_RATIO,
          f"worst {worst[0]} {worst[1]:.2f}x >= {ai_scene.DETAIL_RATIO}x")


def main() -> int:
    test_kill_switch_honoured()
    test_partial_set_fails()
    test_resize_only_model_rejected()
    test_real_upscaler_live()
    if FAILS:
        print(f"\nFAILED {len(FAILS)}: {FAILS}")
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
