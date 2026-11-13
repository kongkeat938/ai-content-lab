#!/usr/bin/env python3
"""Guard the TTS voice fallback in make_short.speak (2026-11-13).

Measured: edge-tts' alternate Thai voice (VOICE_ALT, used for a stalled channel's
recovery probe) returned NoAudioReceived on EVERY retry for certain texts while the
house voice synthesised the same text fine -- a per-voice refusal, not a socket
blip. Retrying the same voice could not recover it, so the whole publish step
failed and a clip was never posted. speak() must fall back to the house voice.

This test drives the REAL speak() with a fake synth (no network): the alt voice
fails, the house voice succeeds, and the clip must still be produced. It fails if
the fallback is removed. `_synth`/`asyncio.sleep` are the only things faked.

    python3 scripts/test_tts_fallback.py     # exit 0 = a clip is never lost to it
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_short as ms  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if ms.VOICE_ALT == ms.VOICE:
        fail("VOICE_ALT must differ from VOICE, or the probe is not an audible change")

    calls: list[str] = []

    async def fake_synth(text: str, out: str, voice: str) -> None:
        calls.append(voice)
        if voice == ms.VOICE_ALT:
            raise RuntimeError("No audio was received. Please verify that your parameters are correct.")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("ok")

    async def no_sleep(_seconds: float) -> None:
        return None

    ms._synth = fake_synth
    ms.asyncio.sleep = no_sleep  # keep the retry backoff out of the test's runtime

    out = tempfile.mktemp(suffix=".mp3")
    try:
        asyncio.run(ms.speak("ข้อความทดสอบ", out, ms.VOICE_ALT))
    except RuntimeError as exc:
        fail(f"speak raised instead of falling back to the house voice: {exc}")

    if not (os.path.exists(out) and os.path.getsize(out) > 0):
        fail("speak produced no audio after the alt-voice refusal")
    if ms.VOICE not in calls:
        fail("speak never tried the house voice as a fallback (the clip would be lost)")

    print(f"OK: alt voice refused, speak fell back to {ms.VOICE} and produced the clip")


if __name__ == "__main__":
    main()
