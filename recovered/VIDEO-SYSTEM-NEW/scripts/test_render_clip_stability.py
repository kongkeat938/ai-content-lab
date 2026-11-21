#!/usr/bin/env python3
"""The clip builder must give the SAME clip twice -- that is what "stable" means.

K, 2026-11-20: "ตอนนี้เราจะวางระบบสร้างคลิปให้ได้มาตรฐานคุณภาพที่นิ่งก่อน" -- a clip
of a stable quality, not a new video every run. Two measured sources of drift had to
be closed before that could be true:

  * `ai_scene.py` sampled with no seed (fixed: `--seed`);
  * `edge_tts` returned different PCM for the same sentence -- 33% of samples
    differed, max 2381 (fixed: a content-addressed `assets/voice_cache`).

So this test asserts the invariant directly, on the real renderer:

  1. two renders of one spec produce a **byte-identical file** (the whole md5);
  2. the second render is **served from the cache** -- no network synthesis, proven
     by a voice cache hit count that must not grow;
  3. the rendered clip **passes `clip_standard`** -- a stable clip that is stable
     and below the floor is not the goal.

Each of these can FAIL: a lost seed, a cache miss, or a renderer change that softens
the picture breaks one of them. Run: python3 scripts/test_render_clip_stability.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FAILS: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def has_ffmpeg() -> bool:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool) and not os.path.exists(f"/tmp/bin/{tool}"):
            return False
    return True


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = "/tmp/bin:" + e.get("PATH", "")
    # The kill switch stays ON for K; this test points it at a path that does not
    # exist so the renderer's real logic can run. test_kill_switch.py fails if a
    # workflow ever sets this variable.
    e["CONTENT_STOP_PATH"] = os.path.join(tempfile.gettempdir(), "no-stop-in-test")
    return e


def run(spec: str, out: str, vault: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, os.path.join(HERE, "render_clip.py"),
                           "--spec", spec, "--out", out, "--vault", vault],
                          capture_output=True, text=True, env=env(), timeout=1800)


def voice_cache_count() -> int:
    return len(glob.glob(os.path.join(ROOT, "assets", "voice_cache", "*.mp3")))


def main() -> int:
    if not has_ffmpeg():
        print("SKIP ffmpeg/ffprobe absent")
        return 0

    images = sorted(glob.glob(os.path.join(ROOT, "assets", "images", "*.jpg")))
    if len(images) < 2:
        print("SKIP need two committed pictures to build a two-shot clip")
        return 0

    work = tempfile.mkdtemp(prefix="stab-")
    spec_path = os.path.join(work, "spec.json")
    spec = {
        "id": "stability-check",
        "channel": "kongkeat-story",
        "title": "ทดสอบความนิ่งของระบบสร้างคลิป",
        "beats": [
            {"image": os.path.relpath(images[0], ROOT),
             "text": "ท้องฟ้ายามเช้าสว่างไสวไปทั่วทุกทิศ"},
            {"image": os.path.relpath(images[1], ROOT),
             "text": "แล้วพระอาทิตย์ก็ขึ้นมาเหนือขอบฟ้า"},
        ],
    }
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False)

    first = os.path.join(work, "a.mp4")
    second = os.path.join(work, "b.mp4")
    r1 = run(spec_path, first)
    if r1.returncode != 0:
        print(r1.stdout[-1500:])
        print(r1.stderr[-2500:])
        check("first render succeeds", False, f"exit {r1.returncode}")
        return 1
    check("first render succeeds", True)

    before = voice_cache_count()
    r2 = run(spec_path, second)
    after = voice_cache_count()
    if r2.returncode != 0:
        print(r2.stderr[-2500:])
        check("second render succeeds", False, f"exit {r2.returncode}")
        return 1
    check("second render succeeds", True)

    check("two renders of one spec are byte-identical", md5(first) == md5(second),
          f"{md5(first)[:12]} vs {md5(second)[:12]}")
    check("the second render needed no new voice synthesis", after == before,
          f"cache {before} -> {after}")

    import clip_standard
    ok, reasons, metrics = clip_standard.verify_clip(first)
    check("the rendered clip meets the standard", ok,
          "; ".join(reasons) if reasons else
          f"{metrics.get('size')} {metrics.get('lufs')} LUFS")

    shutil.rmtree(work, ignore_errors=True)
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
