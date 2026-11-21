#!/usr/bin/env python3
"""Build a 4K-capable scene library with local AI: SD-Turbo -> RealESRGAN.

Why local (measured 2026-11-20, this pod: 4 cores, no GPU):

  * Gemini image models -> HTTP 429, free quota 0 (Lyria music likewise)
  * HF ZeroGPU spaces (FLUX.1-schnell) -> works at 1920x1088 in 13 s, but the
    free allowance is per-IP and was exhausted after ~4 calls; not a base
  * Pollinations -> ignores the requested size, 1 image / 45 s / IP
  * local SD-Turbo -> 640px in ~62 s, unlimited, no quota, no account

Upscaling is a second AI pass, not interpolation: RealESRGAN x4 on a 640px
frame gives 2560px in ~136 s, and it measures as real detail -- edge energy
(mean |gradient|) 12.71 vs 5.02 for a bicubic blow-up of the same frame, i.e.
2.5x more structure. A 2560px frame covers a 3840-wide pan window at 4K, which
is what the video timeline needs.

Usage:
    python3 scripts/ai_scene.py --count 5 --out-dir assets/ai-scenes
    python3 scripts/ai_scene.py --prompt "misty temple at dawn" --count 1 --no-upscale

A generated set is only written when EVERY frame succeeded -- a partial set
must fail, not ship (K's rule).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import kill_switch  # noqa: E402 - the kill switch every rail honours

GEN_PX = 640
SCALE = 4
BASE_MODEL = "stabilityai/sd-turbo"
UPSCALER_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/"
                "v0.1.0/RealESRGAN_x4plus.pth")

# One theme, many angles: the library must be diverse, not five copies of a
# temple. Prompts are data so a run can sweep a whole theme.
THEMES: dict[str, list[str]] = {
    "calm": [
        "a serene Thai temple at dawn, golden mist between white stupas, lotus "
        "pond, warm sunrise light, cinematic photography, ultra detailed",
        "a Buddhist monk in an orange robe walking a stone path at sunrise, soft "
        "fog, ancient Thai temple behind, cinematic photography, ultra detailed",
        "rows of candle flames inside a dark Thai meditation hall, warm amber "
        "glow, deep shadows, smoke haze, cinematic photography, ultra detailed",
        "layered misty mountains at dawn in northern Thailand, floating fog, "
        "pastel sky, a tiny temple on the ridge, cinematic landscape photography",
        "a single pink lotus opening on still dark water at first light, "
        "dewdrops, soft reflection, macro cinematic photography, ultra detailed",
        "a wooden Thai pavilion over still water at sunrise, morning fog, "
        "reflections, cinematic photography, ultra detailed",
        "an old monk's hands holding a palm-leaf manuscript, warm window light, "
        "shallow depth of field, cinematic photography, ultra detailed",
        "rain falling on a stone Buddha face in a forest temple, moss, soft "
        "light, cinematic photography, ultra detailed",
    ],
}


def _require(module: str, hint: str):
    try:
        return __import__(module)
    except ImportError:
        print(f"missing {module}: {hint}", file=sys.stderr)
        raise SystemExit(2)


def edge_energy(image) -> float:
    """Mean absolute gradient -- the measurable difference between detail and blur."""
    import numpy as np

    a = np.asarray(image.convert("L")).astype("float32")
    lap = np.abs(np.diff(a, axis=0)[:, :-1]) + np.abs(np.diff(a, axis=1)[:-1, :])
    return float(lap.mean())


# The gate is a RATIO against a bicubic blow-up of the same frame, never an
# absolute score: an absolute floor measured on one image set is a trap, since
# content with hard edges (a synthetic test card) scores 5.98 after a real
# RealESRGAN pass while soft photography scores 2.44 -- no single number splits
# both. Measured ratios on this pod: real photos 1.33-1.88x, SD-Turbo frames
# 2.53x, a resize-only model exactly 1.00x.
DETAIL_RATIO = 1.15


def detail_ratio(image, upscaled) -> float:
    """How much structure the upscale added, relative to plain interpolation."""
    from PIL import Image

    base = image.convert("RGB").resize(upscaled.size, Image.BICUBIC)
    return edge_energy(upscaled) / max(edge_energy(base), 1e-6)


def ensure_complete(made: list, prompts: list) -> None:
    """A partial set must fail loudly rather than ship (K's rule)."""
    if len(made) != len(prompts):
        raise RuntimeError(f"wrote {len(made)} of {len(prompts)} frames")


def upscale_or_fail(torch, model, image, floor: float = DETAIL_RATIO):
    """Upscale, then refuse the result if it adds no structure over interpolation."""
    import numpy as np
    from PIL import Image

    x = torch.from_numpy(
        np.asarray(image.convert("RGB")).astype("float32") / 255.0
    ).permute(2, 0, 1)[None]
    with torch.no_grad():
        y = model(x)
    arr = (y[0].clamp(0, 1).permute(1, 2, 0).numpy() * 255).round().astype("uint8")
    out = Image.fromarray(arr)
    ratio = detail_ratio(image, out)
    if ratio < floor:
        raise RuntimeError(
            f"upscaler added no detail (ratio {ratio:.2f}x < {floor}x vs bicubic)")
    return out, ratio


def upscaler(weights: str):
    """Load RealESRGAN through spandrel (basicsr will not build on this pod)."""
    torch = _require("torch", "pip install torch --index-url .../whl/cpu")
    _require("spandrel", "pip install spandrel")
    from spandrel import ModelLoader

    if not os.path.exists(weights):
        print(f"fetching upscaler weights -> {weights}", file=sys.stderr)
        import urllib.request
        urllib.request.urlretrieve(UPSCALER_URL, weights)
    torch.set_num_threads(os.cpu_count() or 4)
    return torch, ModelLoader().load_from_file(weights).model.eval()


def store_in_vault(path: str, md5: str, prompt: str, size: list,
                   source: str = "") -> dict:
    """Record a freshly generated picture as FREE stock in the warehouse.

    The vault bans an md5 once a clip takes it, so stock and ban live in one index:
    an entry with `clip` empty is available, an entry with a clip is spent. This is
    what makes the library accumulate instead of being rebuilt per clip.
    """
    import image_vault as V

    with V.lock(V.VAULT):
        data = V.load(V.VAULT)
        rec = data["images"].get(md5, {})
        if rec.get("clip"):
            raise RuntimeError(f"{md5} is already spent by {rec['channel']}/{rec['clip']}")
        rec.update({"channel": "", "clip": "", "file": os.path.basename(path),
                    "prompt": prompt, "size": list(size), "source": source,
                    "stocked_at": V.now()})
        data["images"][md5] = rec
        V.save(data, V.VAULT)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="calm", choices=sorted(THEMES))
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--out-dir", default="assets/ai-scenes")
    ap.add_argument("--weights", default="/tmp/RealESRGAN_x4plus.pth")
    ap.add_argument("--no-upscale", action="store_true")
    a = ap.parse_args()

    if kill_switch.stopped():
        return kill_switch.STOPPED_EXIT

    prompts = [a.prompt] if a.prompt else THEMES[a.theme][:a.count]
    os.makedirs(a.out_dir, exist_ok=True)

    torch = _require("torch", "pip install torch --index-url .../whl/cpu")
    _require("diffusers", "pip install diffusers accelerate")
    from diffusers import AutoPipelineForText2Image
    from PIL import Image

    torch.set_num_threads(os.cpu_count() or 4)
    pipe = AutoPipelineForText2Image.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float32, safety_checker=None)
    pipe.set_progress_bar_config(disable=True)

    torch_up, up = (None, None)
    if not a.no_upscale:
        torch_up, up = upscaler(a.weights)

    made, started = [], time.time()
    for idx, prompt in enumerate(prompts, 1):
        slug = f"{a.theme}-{idx:02d}"
        t = time.time()
        # A pinned seed is per-frame (seed + index), so a run rebuilds exactly the
        # same set of pictures instead of a fresh one that nobody has approved.
        kw = {}
        if a.seed is not None:
            gen = torch.Generator(device="cpu").manual_seed(a.seed + idx)
            kw["generator"] = gen
        img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0,
                   width=GEN_PX, height=GEN_PX, **kw).images[0]

        if up is not None:
            img, score = upscale_or_fail(torch_up, up, img)
            print(f"{slug} detail edge-energy {score:.2f}", flush=True)

        path = os.path.join(a.out_dir, f"{slug}.png")
        img.save(path)
        made.append({"slug": slug, "file": path, "size": list(img.size),
                     "prompt": prompt, "seed": None if a.seed is None else a.seed + idx,
                     "seconds": round(time.time() - t, 1),
                     "edge_energy": None if up is None else round(score, 2)})
        print(f"{slug} {img.size} {made[-1]['seconds']}s", flush=True)

    ensure_complete(made, prompts)

    manifest = os.path.join(a.out_dir, f"{a.theme}.json")
    with open(manifest, "w", encoding="utf-8") as fh:
        json.dump({"theme": a.theme, "model": BASE_MODEL, "gen_px": GEN_PX,
                   "upscale": None if a.no_upscale else SCALE,
                   "total_seconds": round(time.time() - started, 1),
                   "frames": made}, fh, ensure_ascii=False, indent=2)
    print(f"wrote {manifest} ({len(made)} frames, "
          f"{round(time.time() - started)}s total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
