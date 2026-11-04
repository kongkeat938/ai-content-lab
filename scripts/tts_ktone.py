#!/usr/bin/env python3
"""Narration in K's tone of voice, without breaking Thai.

edge-tts speaks the Thai; this repaints the timbre toward K's. The first version
used OpenVoice's tone-colour converter directly and it failed on two counts K
heard and I then measured:

  * it moves the pitch contour, and Thai carries meaning in that contour --
    "ไล่" came back as "ไต่"/"เลย"/"ไร้" and "ทวง" as "ถูก", while the same
    sentences were word-perfect from edge-tts alone. 91-98% word match over the
    first episode.
  * it adds energy below 300 Hz (42% -> 56% of the total) and takes it out of
    1-3 kHz (6.2% -> 1.1%), so the voice reads as dull. Spectral centroid fell
    from 1368 Hz to ~690 Hz against K's own 565 Hz.

So the converter is no longer trusted to produce the output. It is used only as
a *filter estimate*: convert the clip, measure how the converter changed the
spectral envelope, then apply that change to the **original** waveform. The
source keeps its own pitch, harmonics, timing and pauses -- every cue Thai
meaning rides on -- and only the envelope moves.

Measured on this pod (4-core CPU), the problem sentences above:

    "ไล่ขึ้นมาที่ขา"              -> ไล่ขึ้นมาที่ขา      (was ไต่/เลย/ไร้)
    "ลมหายใจไม่เคยทวงบุญคุณ"    -> ...ทวงบุญคุณ        (was ...ถูกบุญคุณ)
    spectral centroid           1368 -> ~880 Hz at alpha=0.55
    similarity to K             0.56 (edge) -> 0.70

The watermark OpenVoice adds by default is switched off: it is a pseudo-random
signal injected into the audio and there is no reason to ship it.

    python3 scripts/tts_ktone.py --build-se work/k_voice/restored/denoised.wav
    python3 scripts/tts_ktone.py --text "สวัสดีครับ" --out /tmp/a.mp3
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
SE_PATH = os.environ.get("K_VOICE_SE", os.path.join(ROOT, "work", "k_voice", "k_se_48k.pth"))

VOICE = "th-TH-NiwatNeural"
RATE, PITCH = "-12%", "-10Hz"
SR = 22050          # OpenVoice's own rate; the envelope is estimated here
NFFT, HOP = 1024, 256
# How far the envelope moves toward K: 0 = edge, 1 = fully K. 0.55 is K's pick
# (2026-11-02) -- bright enough to stop the episode sounding muffled, close
# enough that it still reads as his voice. Override with K_TONE_ALPHA or --alpha.
ALPHA = float(os.environ.get("K_TONE_ALPHA", "0.55"))
ENV_SIGMA_HZ = 350  # envelope smoothing -- below the pitch, above the formants
# The envelope transfer leaves the voice a little soft in the 3-6 kHz band that
# carries consonant clarity; this puts it back without touching the timbre.
CLARITY_EQ = ("highpass=f=90,equalizer=f=2600:t=q:w=1.1:g=5,"
               "equalizer=f=4200:t=q:w=1.3:g=4,equalizer=f=7000:t=q:w=1.6:g=3")

_cvt = None
_se = None
_delta_cache = {}


def available() -> bool:
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
    _cvt.watermark_model = None   # the base class rejects the kwarg; drop it here
    _se = torch.load(SE_PATH, map_location="cpu", weights_only=False)
    return _cvt


def build_se(reference: str, out: str | None = None) -> str:
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


def _envelope(logmag):
    import numpy as np
    from scipy.ndimage import gaussian_filter1d
    import librosa

    freqs = librosa.fft_frequencies(sr=SR, n_fft=NFFT)
    sigma = max(2, int(np.searchsorted(freqs, ENV_SIGMA_HZ)))
    return gaussian_filter1d(logmag, sigma=sigma, axis=0, mode="nearest")


def repaint(src_path: str, out_path: str, alpha: float = ALPHA) -> str:
    """Move `src_path`'s spectral envelope toward K's, keeping everything else."""
    import numpy as np
    import librosa
    import soundfile as sf

    cvt = _load()
    key = (os.path.getsize(src_path), alpha)
    audio = librosa.load(src_path, sr=SR, mono=True)[0]
    spec = librosa.stft(audio, n_fft=NFFT, hop_length=HOP)
    mag, phase = np.abs(spec), np.angle(spec)
    src_lm = np.log(mag + 1e-6)

    if key in _delta_cache:
        delta = _delta_cache[key]
    else:
        converted = cvt.convert(src_path, cvt.extract_se([src_path]), _se,
                                output_path=None, tau=0.5)
        conv_lm = np.log(np.abs(librosa.stft(converted, n_fft=NFFT, hop_length=HOP)) + 1e-6)
        n = min(src_lm.shape[1], conv_lm.shape[1])
        delta = _envelope(conv_lm[:, :n]) - _envelope(src_lm[:, :n])
        _delta_cache[key] = delta

    n = min(src_lm.shape[1], delta.shape[1])
    new_lm = src_lm[:, :n] + alpha * delta
    y = librosa.istft(np.exp(new_lm) * np.exp(1j * phase[:, :n]),
                      hop_length=HOP, length=len(audio))
    sf.write(out_path, np.clip(y, -1, 1), SR)
    return out_path


def synth(text: str, out: str, alpha: float = ALPHA, clarity: bool = True) -> str:
    if not available():
        raise RuntimeError(f"K's tone not ready: need {CKPT}/checkpoint.pth and {SE_PATH}")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    base = os.path.splitext(out)[0]
    src, tone = base + ".src.mp3", base + ".tone.wav"
    _edge_tts(text, src)
    repaint(src, tone, alpha)
    chain = ["-af", CLARITY_EQ] if clarity else []
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tone, *chain,
                    "-ar", "48000", "-b:a", "192k", out], check=True)
    for tmp in (src, tone):
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
    ap.add_argument("--build-se", metavar="RECORDING")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--no-clarity", action="store_true")
    args = ap.parse_args()

    if args.build_se:
        print(f"speaker embedding -> {build_se(args.build_se, args.out)}")
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
    synth(text, args.out, alpha=args.alpha, clarity=not args.no_clarity)
    print(f"{args.out}  {os.path.getsize(args.out) / 1000:.0f} kB  tone=K alpha={args.alpha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
