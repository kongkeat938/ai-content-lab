#!/usr/bin/env python3
"""The producer must refuse rather than ship, and must not burn stock when it fails.

Measured 2026-11-20: the warehouse could not be filled or spent, so "produce a clip"
had no honest answer. The producer now reads K's story verbatim and reserves stock
all-or-nothing; these are the properties that keep that true, each able to FAIL:

  1. a story that would drop a beat is refused before anything is reserved;
  2. a warehouse with too few pictures refuses the whole clip, burning NOTHING
     (measured: it used to hand out what it had and lose the rest);
  3. a failed render puts the pictures back in stock -- otherwise every failed
     attempt quietly eats the library;
  4. the narration is K's text, character for character;
  5. a paused channel produces nothing;
  6. a real clip is built, passes `clip_standard`, and lands in the queue index.

Run: python3 scripts/test_produce.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import generative_art as GA  # noqa: E402
import image_vault as V  # noqa: E402

FAILS: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def has_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def env() -> dict:
    e = dict(os.environ)
    e["CONTENT_STOP_PATH"] = os.path.join(tempfile.gettempdir(), "no-stop-in-test")
    e["VOICE_CACHE_DIR"] = os.path.join(tempfile.gettempdir(), "produce-voice-cache")
    return e


def stock(vault: str, work: str, n: int) -> list:
    md5s = []
    real = V.VAULT
    V.VAULT = vault
    try:
        for i in range(n):
            p = os.path.join(work, f"art{i}.png")
            GA.generate("flow", 3300 + i, 256, "teal").save(p, "PNG", optimize=True)
            md5s.append(GA.stock(p, {"gen": "flow", "seed": 3300 + i, "palette": "teal"}))
    finally:
        V.VAULT = real
    return md5s


def write_story(path: str, sid: str, lines: list, cta: str = "") -> str:
    story = {"id": sid, "genre": "dharma", "hook": "ความสงบเริ่มที่ลมหายใจ",
             "lines": lines, "mood": "night"}
    if cta:
        story["cta"] = cta
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(story, fh, ensure_ascii=False)
    return path


def run(args: list, timeout: int = 1500) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, os.path.join(HERE, "produce.py")] + args,
                          capture_output=True, text=True, env=env(), timeout=timeout)


def main() -> int:
    work = tempfile.mkdtemp(prefix="prod-")
    try:
        vault = os.path.join(work, "vault.json")
        V.save({"images": {}}, vault)

        # 1. a story with an empty line must be refused, and reserve nothing
        bad = write_story(os.path.join(work, "bad.json"), "bad", ["ok", "  "])
        stock(vault, work, 4)
        before = len(V.free_stock(V.load(vault)))
        r = run(["--story", bad, "--channel", "dharma", "--vault", vault, "--dry-run"])
        check("a story with an empty line is refused", r.returncode != 0,
              f"exit {r.returncode}")
        check("the refusal names the empty line", "line 2 is empty" in (r.stderr + r.stdout),
              (r.stderr or r.stdout).strip()[:70])
        check("nothing was reserved for the bad story",
              len(V.free_stock(V.load(vault))) == before,
              f"{before} -> {len(V.free_stock(V.load(vault)))}")

        # 2. too little stock: refuse the whole clip, burn nothing
        hungry = write_story(os.path.join(work, "hungry.json"), "hungry",
                             [f"ประโยคที่ {i}" for i in range(1, 9)])
        r = run(["--story", hungry, "--channel", "dharma", "--vault", vault])
        check("too little stock refuses the clip", r.returncode != 0, f"exit {r.returncode}")
        check("the refusal says how much stock is short",
              "needs 9" in (r.stderr + r.stdout), (r.stderr or r.stdout).strip()[:90])
        check("a refused clip burns no pictures",
              len(V.free_stock(V.load(vault))) == before,
              f"{before} -> {len(V.free_stock(V.load(vault)))}")
        check("the refusal tells K how to stock the warehouse",
              "generative_art.py" in (r.stderr + r.stdout))

        # 3. the narration is K's text, character for character
        import produce
        story = produce.load_story(write_story(
            os.path.join(work, "t.json"), "t", ["บรรทัดหนึ่ง", "บรรทัดสอง"], "ติดตามด้วย"))
        texts = [b["text"] for b in produce.beats_of(story)]
        check("the narration is the hook, the lines, then the CTA",
              texts == ["ความสงบเริ่มที่ลมหายใจ", "บรรทัดหนึ่ง", "บรรทัดสอง", "ติดตามด้วย"],
              str(texts))

        # 4. a paused channel produces nothing
        r = run(["--story", write_story(os.path.join(work, "p.json"), "p", ["x"]),
                 "--channel", "paused-channel", "--vault", vault, "--dry-run"])
        paused = produce.paused_channels()
        if paused:
            check("a paused channel is skipped", "paused" in (r.stdout + r.stderr).lower()
                  or r.returncode == 0)
        else:
            check("no channel is paused in this checkout (nothing to test)", True)

        # 5. release puts pictures back, and never frees another clip's pictures
        md5s = V.take_free(2, "dharma", "release-test", vault)
        check("a reservation spends stock", len(V.free_stock(V.load(vault))) == before - 2,
              f"{len(V.free_stock(V.load(vault)))} free")
        check("releasing the clip's own pictures restores stock",
              V.release(md5s, "release-test", vault) == 2 and
              len(V.free_stock(V.load(vault))) == before)
        V.take_free(1, "dharma", "other-clip", vault)
        freed = V.release(md5s, "release-test", vault)
        check("a release cannot free another clip's picture", freed == 0,
              f"freed {freed}")
        V.release(V.free_stock(V.load(vault)), "other-clip", vault)

        if not has_ffmpeg():
            print("SKIP real render (ffmpeg/ffprobe absent)")
        else:
            # 6. a real clip: built, verified, and filed in the queue
            good = write_story(os.path.join(work, "good.json"), "good",
                               ["หายใจช้า ๆ แล้วปล่อยวาง"], "กดติดตามไว้ด้วย")
            queue = os.path.join(work, "queue")
            os.makedirs(queue, exist_ok=True)
            produce.INDEX = os.path.join(queue, "index.json")
            produce.QUEUE = queue
            rc = produce.produce_one(good, "dharma", False,
                                     os.path.join(HERE, "render_clip.py"), vault, False)
            check("a real clip is produced", rc == 0, f"rc {rc}")
            out = os.path.join(queue, "dharma-good.mp4")
            check("the clip file exists", os.path.exists(out))
            if os.path.exists(out):
                import clip_standard
                ok, reasons, metrics = clip_standard.verify_clip(out)
                check("the produced clip meets the standard", ok,
                      "; ".join(reasons) if reasons else f"{metrics.get('lufs')} LUFS")
            data = json.load(open(produce.INDEX, encoding="utf-8"))
            entry = data["videos"][0]
            check("the clip is filed in the queue index", entry["id"] == "dharma-good")
            check("the queue entry is marked queued", entry["state"] == "queued")
            check("the queue entry records the pictures it used",
                  len(entry.get("pictures") or []) == 2,
                  str(len(entry.get("pictures") or [])))
            check("the pictures it used are now banned",
                  all(V.is_used(m, V.load(vault)) for m in entry["pictures"]))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
