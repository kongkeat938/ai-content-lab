#!/usr/bin/env python3
"""Narration in K's tone of voice, cloned on the pod -- no key, no GPU, no fee.

edge-tts writes the Thai words; OpenVoice's tone-colour converter repaints them
with K's timbre, taken from the recording he sent. The words are synthesiser-
made, the voice is his, so a whole night video can be narrated in his tone from
one short sample.

Why this and not a text-to-speech clone (measured 2026-11-03):
  * XTTS/GPT-SoVITS/F5-TTS have no Thai; the Thai-capable ones need a GPU.
  * Fish Audio clones Thai on the free tier, but needs K's API key.
  * OpenVoice v2 is a *tone converter*: it never sees Thai phonemes, only the
    source waveform, so it is language-agnostic. Measured on this pod's 4-core
    CPU: 9.4 s to convert a 10 s clip, speaker similarity 0.56 -> 0.88, F0
    141.6 Hz -> 111.1 Hz against K's 117.6 Hz, and the Thai came back word-perfect
    on a re-transcription.

Setup (once, already done in this workspace):
    /workspace/OpenVoice            # repo + checkpoints_v2/converter
    work/k_voice/k_se.pth           # K's speaker embedding

    python3 scripts/tts_openvoice.py --build-se work/k_voice/k_raw.wav
    python3 scripts/tts_openvoice.py --text "สวัสดีครับ" --out /tmp/a.mp3
    python3 scripts/tts_openvoice.py --script content/ch2_shorts/scripts.json \
        --index 32 --out work/ch2_shorts/32/voice.mp3

make_short.py and make_audio.py pick this up automatically when the embedding
exists and NARRATOR=openvoice is set, so a whole episode can be voiced in K's
tone without touching the pipeline.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OPENVOICE_DIR = os.environ.get("OPENVOICE_DIR", "/workspace/OpenVoice")
CKPT = os.path.join(OPENVOICE_DIR, "checkpoints_v2", "converter")
SE_PATH = os.environ.get("K_VOICE_SE", os.path.join(ROOT, "work", "k_voice", "k_se.pth"))

VOICE = "th-TH-NiwatNeural"      # the words come from the house voice
RATE = "-15%"
PITCH = "-8Hz"                   # edges the source toward K's register
TAU = 0.5                        # tone-mix strength; 0.5 measured best here

_cvt = None
_se = None


def available() -> bool:
    """True when the converter and K's embedding are both in place."""
    return os.path.exists(os.path.join(CKPT, "checkpoint.pth")) and os.path.exists(SE_PATH)


def _load():
    global _cvt, _se
    if _cvt is not None:
        return _cvt
    if OPENVOICE_DIR not in sys.path:
        sys.path.insert(0, OPENVOICE_DIR)
    import torch
    from openvoice.api import ToneColorConverter

    _cvt = ToneColorConverter(os.path.join(CKPT, "config.json"), device="cpu")
    _cvt.load_ckpt(os.path.join(CKPT, "checkpoint.pth"))
    _se = torch.load(SE_PATH, map_location="cpu", weights_only=False)
    return _cvt


def build_se(reference: str, out: str | None = None) -> str:
    """Extract K's speaker embedding from a recording and save it."""
    _load()
    import torch

    se = _cvt.extract_se([reference])
    dest = out or SE_PATH
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    torch.save(se.cpu(), dest)
    return dest


def _edge_tts(text: str, out: str) -> None:
    import edge_tts

    async def go():
        c = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
        with open(out, "wb") as fh:
            async for chunk in c.stream():
                if chunk["type"] == "audio":
                    fh.write(chunk["data"])

    asyncio.run(go())


def synth(text: str, out: str, tau: float = TAU) -> str:
    """Speak `text` and repaint it in K's tone. Writes an mp3 at `out`."""
    if not available():
        raise RuntimeError(f"OpenVoice not ready: need {CKPT}/checkpoint.pth and {SE_PATH}")
    cvt = _load()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    src = os.path.splitext(out)[0] + ".src.mp3"
    raw = os.path.splitext(out)[0] + ".tone.wav"
    _edge_tts(text, src)
    cvt.convert(src, cvt.extract_se([src]), _se, output_path=raw, tau=tau)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw,
                    "-ar", "48000", "-b:a", "192k", out], check=True)
    for tmp in (src, raw):
        if os.path.exists(tmp):
            os.remove(tmp)
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
    ap.add_argument("--out")
    ap.add_argument("--build-se", metavar="RECORDING",
                    help="extract K's speaker embedding from a recording and stop")
    ap.add_argument("--tau", type=float, default=TAU)
    args = ap.parse_args()

    if args.build_se:
        dest = build_se(args.build_se, args.out)
        print(f"speaker embedding -> {dest}")
        return 0

    if not args.out:
        sys.exit("--out is required")
    if args.script:
        if not args.index:
            sys.exit("--index is required with --script")
        text = text_for(args.script, args.index)
    elif args.text:
        text = args.text
    else:
        sys.exit("give --text or --script/--index")

    synth(text, args.out, tau=args.tau)
    print(f"{args.out}  {os.path.getsize(args.out) / 1000:.0f} kB  tone=K")
    return 0


if __name__ == "__main__":
    sys.exit(main())
