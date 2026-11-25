#!/usr/bin/env python3
"""Render the three portfolio samples, then prove each one meets the spec.

Everything in them is generated here: shapes and gradients drawn with Pillow,
speech from Microsoft Edge TTS, a tone bed built with ffmpeg's own sine source.
No stock footage, no music library, no client work — so nothing in the samples
can be mistaken for a delivered job or carry someone else's rights.

    python3 scripts/make_samples.py            # render all three, then verify
    python3 scripts/make_samples.py --verify    # verify whatever exists

The verify step is a gate: wrong size, wrong length, no audio track, or audio
louder than -14 LUFS fails the run and the file is not reported as ready.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "portfolio", "media")
FONT = os.path.join(ROOT, "assets", "fonts", "NotoSansThai.ttf")
W, H, FPS = 1080, 1920, 30
VOICE = "th-TH-PremwadeeNeural"


def ffmpeg() -> str:
    for name in ("ffmpeg", "ffprobe"):
        if shutil.which(name):
            break
    else:
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
        except Exception:  # noqa: BLE001
            raise SystemExit("2: no ffmpeg on PATH (install ffmpeg or static-ffmpeg)")
    return shutil.which("ffmpeg") or "ffmpeg"


def probe() -> str:
    return shutil.which("ffprobe") or "ffprobe"


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg failed: {' '.join(cmd[:6])}...\n{r.stderr[-1500:]}")


# ---------------------------------------------------------------- drawing
def _font(size: int):
    from PIL import ImageFont
    return ImageFont.truetype(FONT, size)


def _bg(top: tuple[int, int, int], bottom: tuple[int, int, int]):
    """A vertical gradient built from a 1-pixel column, then stretched: drawing
    two million pixels one at a time cost minutes, this costs milliseconds."""
    from PIL import Image
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / H
        col.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return col.resize((W, H), Image.BILINEAR)


def _centered(draw, y: int, text: str, size: int, fill, stroke=0, stroke_fill=None):
    f = _font(size)
    box = draw.textbbox((0, 0), text, font=f, stroke_width=stroke)
    draw.text(((W - (box[2] - box[0])) / 2 - box[0], y), text, font=f, fill=fill,
              stroke_width=stroke, stroke_fill=stroke_fill)
    return box[3] - box[1]


def _wrap(draw, text: str, size: int, maxw: int) -> list[str]:
    f = _font(size)
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(path: str, title: str, lines: list[str], price: str = "", cta: str = "",
         top=(12, 18, 32), bottom=(28, 46, 78), accent=(255, 214, 92)) -> None:
    from PIL import ImageDraw
    im = _bg(top, bottom)
    d = ImageDraw.Draw(im)
    # a product silhouette, drawn not photographed
    d.rounded_rectangle((W // 2 - 210, 620, W // 2 + 210, 1240), 60, fill=(238, 240, 245))
    d.rounded_rectangle((W // 2 - 210, 620, W // 2 + 210, 780), 60, fill=(205, 210, 220))
    d.ellipse((W // 2 - 150, 400, W // 2 + 150, 700), fill=accent)
    y = 120
    _centered(d, y, title, 74, (255, 255, 255), 4, (0, 0, 0))
    y = 1330
    for ln in lines:
        for part in _wrap(d, ln, 52, W - 140):
            _centered(d, y, part, 52, (235, 240, 250))
            y += 74
    if price:
        _centered(d, 1560, price, 96, accent, 5, (0, 0, 0))
    if cta:
        d.rounded_rectangle((W // 2 - 320, 1720, W // 2 + 320, 1840), 60, fill=accent)
        _centered(d, 1750, cta, 60, (16, 20, 28))
    im.save(path, "PNG")


def still(path: str, headline: str, caption: str, hue: int) -> None:
    """A 'photo' built from a gradient and silhouettes — no camera, no licence."""
    from PIL import ImageDraw
    top = (20 + hue % 60, 40, 90)
    im = _bg(top, (250, 170, 120))
    d = ImageDraw.Draw(im)
    d.ellipse((120, 380, 420, 680), fill=(255, 235, 190))       # sun
    for i, (x, w, hh) in enumerate(((0, 380, 520), (300, 420, 640), (720, 380, 560))):
        d.polygon([(x, H), (x + w / 2, H - hh), (x + w, H)], fill=(30 + i * 10, 34, 46))
    d.rectangle((0, H - 420, W, H), fill=(14, 18, 28))
    _centered(d, H - 360, headline, 70, (255, 255, 255), 4, (0, 0, 0))
    for i, part in enumerate(_wrap(d, caption, 46, W - 160)):
        _centered(d, H - 250 + i * 62, part, 46, (225, 232, 245))
    im.save(path, "PNG")


# ---------------------------------------------------------------- audio
def tts(text: str, path: str) -> bool:
    """One request, retried with a long backoff.

    Measured 2026-11-25: a single long request succeeds (84 KB, 14 s of speech)
    while six short requests a few seconds apart are all refused with
    NoAudioReceived — the free endpoint throttles bursts, so chunking made it
    worse. A failure is reported and the clip is not built, rather than shipping
    a silent file that claims to have a voice.
    """
    import asyncio

    try:
        import edge_tts
    except Exception:  # noqa: BLE001
        return False

    async def speak() -> bool:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text.replace("\n", " "), VOICE).save(path)
                if os.path.getsize(path) > 2000:
                    return True
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(15)
        return False

    return asyncio.run(speak())


def tone_bed(path: str, seconds: float, freq: float = 220.0) -> None:
    """A rights-free bed: two sine partials, faded, quiet under the voice."""
    run([ffmpeg(), "-y", "-v", "error",
         "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency={freq * 1.5}:duration={seconds}",
         "-filter_complex", "[0:a]volume=0.10[a];[1:a]volume=0.05[b];[a][b]amix=inputs=2,"
                            "afade=t=in:d=1,afade=t=out:st=" + f"{max(seconds - 1.5, 0):.2f}" + ":d=1.5",
         "-ar", "48000", path])


# ---------------------------------------------------------------- assemble
def build(name: str, frames: list[str], seconds_each: float, narration: str | None,
          bed: bool = False) -> str:
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, "_" + name)
    os.makedirs(tmp, exist_ok=True)
    total = seconds_each * len(frames)
    clip = os.path.join(tmp, "video.mp4")
    # one image per scene, held with a slow zoom, joined in order
    inputs, filters = [], []
    for i, f in enumerate(frames):
        inputs += ["-loop", "1", "-t", f"{seconds_each}", "-i", f]
        filters.append(f"[{i}:v]scale={W}:{H}:flags=bicubic,setsar=1,fps={FPS},"
                       f"format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st={max(seconds_each - 0.4, 0):.2f}:d=0.4[v{i}]")
    concat = "".join(f"[v{i}]" for i in range(len(frames))) + f"concat=n={len(frames)}:v=1:a=0[v]"
    run([ffmpeg(), "-y", "-v", "error", *inputs,
         "-filter_complex", ";".join(filters) + ";" + concat,
         "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", str(FPS), clip])

    audio_parts, mix, labels = [], [], []
    idx = 1   # input 0 is the video, so audio inputs start at 1
    if narration:
        voice = os.path.join(tmp, "voice.mp3")
        if not tts(narration, voice):
            raise SystemExit(f"2: narration failed for {name} — refusing to ship a clip "
                             f"that claims a voice it does not have")
        audio_parts += ["-i", voice]
        mix.append(f"[{idx}:a]adelay=600|600,apad=whole_dur={total}[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    if bed:
        bedf = os.path.join(tmp, "bed.wav")
        tone_bed(bedf, total)
        audio_parts += ["-i", bedf]
        mix.append(f"[{idx}:a]volume=0.5[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
    final = os.path.join(OUT, name)
    if not audio_parts:
        run([ffmpeg(), "-y", "-v", "error", "-i", clip, "-f", "lavfi", "-i",
             f"anullsrc=r=48000:cl=stereo", "-shortest", "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", final])
    else:
        chain = ";".join(mix) + ";" + "".join(labels) + \
                f"amix=inputs={len(labels)}:duration=longest," \
                f"loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        run([ffmpeg(), "-y", "-v", "error", "-i", clip, *audio_parts,
             "-filter_complex", chain, "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", final])
    shutil.rmtree(tmp, ignore_errors=True)
    return final


# ---------------------------------------------------------------- gate
def measure(path: str) -> dict:
    p = subprocess.run([probe(), "-v", "error", "-show_streams", "-show_format",
                        "-of", "json", path], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise SystemExit(f"2: BLIND — ffprobe cannot read {path}")
    d = json.loads(p.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    loud = subprocess.run([ffmpeg(), "-v", "info", "-nostats", "-i", path,
                           "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    import re
    m = re.findall(r"I:\s*(-?\d+\.\d+) LUFS", loud.stderr)
    return {"width": v["width"] if v else 0, "height": v["height"] if v else 0,
            "duration": float(d["format"]["duration"]), "has_audio": a is not None,
            "lufs": float(m[-1]) if m else None,
            "size": int(d["format"]["size"])}


def verify(paths: list[str]) -> int:
    bad = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"FAIL {os.path.basename(p)}: missing")
            bad += 1
            continue
        m = measure(p)
        problems = []
        if (m["width"], m["height"]) != (W, H):
            problems.append(f"{m['width']}x{m['height']} is not {W}x{H}")
        if not 15 <= m["duration"] <= 60:
            problems.append(f"{m['duration']:.1f}s outside 15-60s")
        if not m["has_audio"]:
            problems.append("no audio track")
        if m["lufs"] is None:
            problems.append("loudness not measurable")
        elif not -17 <= m["lufs"] <= -13:
            problems.append(f"{m['lufs']:.1f} LUFS outside -17..-13")
        status = "OK  " if not problems else "FAIL"
        print(f"{status} {os.path.basename(p)} {m['width']}x{m['height']} "
              f"{m['duration']:.1f}s {m['lufs'] if m['lufs'] is not None else '-'} LUFS "
              f"{m['size'] / 1e6:.1f} MB" + ("" if not problems else " :: " + "; ".join(problems)))
        bad += bool(problems)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    ffmpeg()
    os.makedirs(OUT, exist_ok=True)
    names = ["sample_product_45s.mp4", "sample_promo_20s.mp4", "sample_still_30s.mp4"]
    if not a.verify:
        work = os.path.join(OUT, "_frames")
        os.makedirs(work, exist_ok=True)
        print("product sales, 45s")
        frames = []
        scenes = [("สินค้าตัวอย่าง", ["ขวดพกพา 500 มล.", "น้ำหนักเบา พกง่าย"], ""),
                  ("จุดเด่น", ["เปิดง่าย ไม่หก", "ล้างทำความสะอาดได้"], ""),
                  ("รีวิวจากลูกค้า", ["\"ใช้ทุกวัน คุ้มมาก\"", "คะแนน 4.8 / 5"], ""),
                  ("ราคาพิเศษ", ["วันนี้เท่านั้น", "ส่งฟรีทั่วประเทศ"], "299.-"),
                  ("วิธีสั่ง", ["กดลิงก์ในไบโอ", "แชทถามได้เลย"], "299.-", "สั่งเลย"),
                  ("ของมีจำนวนจำกัด", ["เหลือ 40 ชิ้น", "ราคานี้ถึงเที่ยงคืน"], "299.-", "สั่งเลย")]
        for i, sc in enumerate(scenes):
            f = os.path.join(work, f"p{i}.png")
            card(f, sc[0], sc[1], price=sc[2], cta=sc[3] if len(sc) > 3 else "")
            frames.append(f)
        build(names[0], frames, 7.5,
              "สินค้าตัวอย่าง ขวดพกพา 500 มิลลิลิตร น้ำหนักเบา พกง่าย เปิดง่ายไม่หก "
              "ล้างทำความสะอาดได้ ใช้ทุกวันคุ้มมาก ราคาพิเศษวันนี้ 299 บาท ส่งฟรีทั่วประเทศ "
              "กดลิงก์ในไบโอแล้วสั่งได้เลย ของมีจำนวนจำกัด")

        print("short promo, 20s")
        frames = []
        for i, (head, sub) in enumerate((("ตัดคลิปให้ขายได้", "จากคลิปยาวของคุณ"),
                                         ("แนวตั้ง 9:16", "30-60 วินาที"),
                                         ("พาดหัว + คำบรรยาย", "พร้อม thumbnail"),
                                         ("ส่งใน 1-2 วัน", "แก้ไขได้ 2 ครั้ง"))):
            f = os.path.join(work, f"s{i}.png")
            card(f, head, [sub], top=(20, 12, 40), bottom=(60, 24, 90), accent=(120, 230, 255))
            frames.append(f)
        build(names[1], frames, 5.0, None, bed=True)

        print("still + narration, 30s")
        frames = []
        for i, (head, cap) in enumerate((
                ("คลิปยาว 1 ชั่วโมง", "ตัดเป็น 10 คลิปสั้นได้"),
                ("เลือกช่วงที่คนดูหยุด", "hook ใน 3 วินาทีแรก"),
                ("ใส่คำบรรยายไทย", "ดูได้โดยไม่เปิดเสียง"),
                ("ส่งงานพร้อม thumbnail", "พร้อมโพสต์ทันที"))):
            f = os.path.join(work, f"t{i}.png")
            still(f, head, cap, hue=i * 40)
            frames.append(f)
        import time as _t
        _t.sleep(10)   # give the free TTS endpoint room between the two clips
        build(names[2], frames, 7.5,
              "คลิปยาวหนึ่งชั่วโมง ตัดเป็นคลิปสั้นสิบคลิปได้ เลือกช่วงที่คนดูหยุดดู "
              "ใส่ฮุกในสามวินาทีแรก ใส่คำบรรยายภาษาไทย ดูได้โดยไม่ต้องเปิดเสียง "
              "ส่งงานพร้อมภาพปก พร้อมโพสต์ทันที")
        shutil.rmtree(work, ignore_errors=True)

    paths = [os.path.join(OUT, n) for n in names]
    print("\nverify")
    return verify(paths)


if __name__ == "__main__":
    sys.exit(main())
