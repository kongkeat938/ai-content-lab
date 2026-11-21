# 06 — Local AI image + music generation (measured 2026-11-20)

Companion to `scripts/ai_scene.py`, `scripts/ai_music.py`, `docs/VIDEO-SYSTEM-NEW.md`.
Every number here was measured in this pod (4 cores, 15 GB RAM, no GPU). Pods recycle and
`/tmp` is wiped — that is why this file exists.

## Routes that do NOT work (re-measured, so nobody tries again)

| Route | Result |
|---|---|
| Gemini image (`gemini-3.1-flash-image`, `-2.5-flash-image`) | HTTP **429, free quota 0** |
| Gemini Lyria (`lyria-3-clip-preview`, `lyria-3.5`) | **429, quota 0** |
| HF ZeroGPU space `black-forest-labs/FLUX.1-schnell` via `gradio_client` | **works**: 1360×768 in 5.7 s, 1920×1088 in 13.1 s — but the free allowance is per-IP and dies after ~4 calls (`AppError ... ZeroGPU runs limit`) |
| HF Spaces upscalers (`not-lain/RealESRGAN`, `Wuvin/SUPIR`, `yuvid108c/4k-video-upscaler`, …) | **401** — not running / gated. A `/api/spaces?search=upscale` sweep returned **0 RUNNING** |
| Pollinations audio | returns text, not audio |
| `pip install realesrgan` | **fails** — `basicsr` will not build (needs old torchvision) |

## What works, and its cost

- **SD-Turbo** (`stabilityai/sd-turbo`, diffusers, `num_inference_steps=4`,
  `guidance_scale=0.0`): 512 px ≈ 39 s, **640 px ≈ 62 s**, 768 px ≈ 91.5 s, 1024 px ≈ 182.6 s.
- **RealESRGAN x4** through **`spandrel`** (not `basicsr`): weights
  `RealESRGAN_x4plus.pth` 67 MB from the xinntao GitHub release; **640 → 2560 px in 136 s**.
- **MusicGen** small: **20.42 s of audio in 144 s**; `-22.6 LUFS, LRA 1.8`.

## Trap: torch / torchvision must be a matched pair

`transformers` pulls a torchvision built against a different torch, and the symptom is
`RuntimeError: operator torchvision::nms does not exist` — which surfaces as a misleading
`Failed to import diffusers.pipelines.auto_pipeline`. Working pair measured:
`torch==2.9.0+cpu` + `torchvision==0.24.0+cpu` from `download.pytorch.org/whl/cpu`.
`transformers==4.44.2` fails to build (`tokenizers`); 5.23.0 works.

## Trap: an absolute "detail" threshold is worthless

The first detail gate used `edge_energy >= 8.0`. Measured:
synthetic hard-edged card after a **real** RealESRGAN pass = **5.98** (falsely rejected);
soft photography after a real pass = **2.44** (so no constant above 2.44 can also accept 5.98
in a useful way). Fix: compare against a **bicubic blow-up of the same frame** — a ratio.
Measured ratios: repo photography **1.36–1.88×**, SD-Turbo frames **2.53×**, resize-only model
**1.11×**. Gate at **1.15×**.

## Trap: `-stream_loop -1` + `-shortest` does not make a longer file

`test_night.py` built its "video longer than audio" case that way and the output was exactly
the audio length, so the guard could never fail. Build the defect with an explicit
`-t <audio + 4>` instead. (The verifier itself was correct all along — it reports
`video/audio length differ by 4.00s`.)

## Environment gaps on a fresh pod (not code defects)

- `ffprobe` missing → **12** tests fail. `apt-get` is not permitted (no root). Fix: download
  `ffmpeg-master-latest-linux64-gpl.tar.xz` from the BtbN builds release and copy
  `ffmpeg`+`ffprobe` into `/tmp/bin`.
- `edge-tts` missing → narration fails. `googleapiclient` missing → `test_shorts_cta_comment`
  fails.
- Full suite with those present: **111/111 pass**.

## The demo that proves the chain

`/tmp/demo1/build_multi.sh`: 5 AI scenes → 720p timeline, crossfades, Thai narration,
AI music, two-pass `loudnorm`. Measured: 19.000 s, 1280×720 yuv420p(tv, bt709), 25 fps,
−14.9 LUFS, true peak −1.5 dBFS, LRA 5.8, last-quarter frame-diff 0.98 (motion to the end).
