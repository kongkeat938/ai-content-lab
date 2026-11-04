#!/usr/bin/env python3
"""Thai narration in K's cloned voice, via Fish Audio's free developer tier.

edge-tts (th-TH-NiwatNeural) is the house voice and stays the default. This is
the optional second voice: K's own, so the channel can sound like a person
instead of a synthesiser.

Why Fish Audio and not a local model (measured 2026-11-03):
  * XTTS v2, GPT-SoVITS and F5-TTS have no Thai at all; the Thai-capable ones
    (ThonburianTTS, Qwen3-TTS, JaiTTS) are not free to clone with.
  * Local cloning is 30-50x slower than real time on CPU, and both the pod and
    PC1 have no GPU. A 120-minute night video would take 60-100 hours.
  * Fish Audio clones from a short sample and speaks Thai on the free
    `s2.1-pro-free` model (same model as paid, fair-use, no hard cap).

Setup (once):
  1. Record ~30-60 s of clean speech in a quiet room (phone memo is fine).
  2. fish.audio -> sign in -> Voices -> create a voice from that sample.
  3. Put the API key and the voice id in the environment:
         FISH_API_KEY=...  FISH_REFERENCE_ID=...

    python3 scripts/tts_fish.py --text "สวัสดีครับ" --out /tmp/a.mp3
    python3 scripts/tts_fish.py --script content/ch2_shorts/scripts.json \
        --index 32 --out work/ch2_shorts/32/voice.mp3

The output is raw synthesis at the service's own level; the mastering chain in
make_audio.py still runs afterwards, so the -14 LUFS / -3 dBTP gate is unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.fish.audio/v1/tts"
MODEL = "s2.1-pro-free"          # the free developer tier; same model as paid


def available() -> bool:
    return bool(os.environ.get("FISH_API_KEY") and os.environ.get("FISH_REFERENCE_ID"))


def synth(text: str, out: str, api_key: str | None = None,
          reference_id: str | None = None, timeout: int = 180) -> str:
    """Synthesise `text` to an mp3 at `out`. Raises if the voice is not set up."""
    api_key = api_key or os.environ.get("FISH_API_KEY")
    reference_id = reference_id or os.environ.get("FISH_REFERENCE_ID")
    if not api_key or not reference_id:
        raise RuntimeError("FISH_API_KEY and FISH_REFERENCE_ID must both be set")

    body = json.dumps({
        "text": text,
        "reference_id": reference_id,
        "format": "mp3",
        "mp3_bitrate": 128,
        "normalize": True,
        "prosody": {"speed": 1.0, "normalize_loudness": True},
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": MODEL,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            data = fh.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Fish Audio {exc.code}: {detail}") from exc
    if len(data) < 2000:
        raise RuntimeError(f"Fish Audio returned {len(data)} bytes -- not audio")
    with open(out, "wb") as fh:
        fh.write(data)
    return out


def text_for(scripts_path: str, index: str) -> str:
    with open(scripts_path, encoding="utf-8") as fh:
        scripts = json.load(fh)
    for s in scripts:
        if s["id"] == index:
            return "\n".join([s["hook"], *s["lines"], s["cta"]])
    raise SystemExit(f"no script with id {index} in {scripts_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--script")
    ap.add_argument("--index")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.script:
        if not args.index:
            sys.exit("--index is required with --script")
        text = text_for(args.script, args.index)
    elif args.text:
        text = args.text
    else:
        sys.exit("give --text or --script/--index")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    synth(text, args.out)
    print(f"{args.out}  {os.path.getsize(args.out) / 1000:.0f} kB  "
          f"voice={os.environ.get('FISH_REFERENCE_ID')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
