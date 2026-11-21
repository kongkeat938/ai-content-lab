#!/usr/bin/env python3
"""AI-generated music, locally, with no quota and no third-party service.

K's rule (2026-11-20): music must be AI-generated -- the downloaded "beds" in
assets/music are not to be used. Every hosted route was measured and refused:

  * Gemini Lyria (`lyria-3-clip-preview`, `lyria-3.5`) -> HTTP 429, free quota 0
  * HuggingFace inference, no token -> no route (and 401 on the router endpoint)
  * Pollinations audio -> text, not music

So the model runs here: `facebook/musicgen-small` through transformers, on CPU.
Measured on this pod (4 cores, torch 2.15 cpu):
  * load 18 s, 5 s of audio in 31 s, 20 s of audio in 144 s -- roughly 7x realtime
  * output is real music, not a tone: -22.6 LUFS, LRA 1.8 LU, zero-crossing
    rate 0.012 (a sine beep reads near 0.05+ and LRA ~0)

Usage:
    python3 scripts/ai_music.py --seconds 20 --out music.wav
    python3 scripts/ai_music.py --seconds 20 --prompt "tense drone, low strings"
"""
from __future__ import annotations

import argparse
import os
import sys

import kill_switch  # noqa: E402 - the kill switch every rail honours

DEFAULT_PROMPT = ("calm ambient meditation music, soft warm pads, no drums, slow, "
                  "serene, gentle piano notes, peaceful night atmosphere")
# musicgen emits 50 tokens per second of audio (EnCodec at 50 Hz).
TOKENS_PER_SECOND = 50


def build(prompt: str, seconds: int, out: str, guidance: float = 3.0,
          seed: int | None = None) -> str:
    import torch
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    import scipy.io.wavfile as wavfile

    torch.set_num_threads(os.cpu_count() or 4)
    if seed is not None:
        torch.manual_seed(seed)

    name = os.environ.get("MUSICGEN_MODEL", "facebook/musicgen-small")
    processor = AutoProcessor.from_pretrained(name)
    model = MusicgenForConditionalGeneration.from_pretrained(name)

    inputs = processor(text=[prompt], return_tensors="pt", padding=True)
    with torch.no_grad():
        audio = model.generate(**inputs,
                               max_new_tokens=seconds * TOKENS_PER_SECOND,
                               do_sample=True, guidance_scale=guidance)

    rate = model.config.audio_encoder.sampling_rate
    wavfile.write(out, rate, audio[0, 0].numpy())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()

    if kill_switch.stopped():
        return kill_switch.STOPPED_EXIT

    if a.seconds > 30:
        print("refusing: >30 s on CPU costs minutes per clip; generate in pieces",
              file=sys.stderr)
        return 2

    path = build(a.prompt, a.seconds, a.out, seed=a.seed)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
