#!/usr/bin/env python3
"""Grade a finished video with Gemini vision -- sample frames, ask, print a verdict.

The one judgement this repo cannot make with a formula is "does the picture look
good?". A vision model can, but its score is NOT reproducible: measured 2026-11-17,
the same unchanged cut scored 9 then 5/10, so it must never gate CI. This tool is
the deliberate, manual counterpart -- ak runs it, reads the number, and decides.

It samples N frames evenly across the file (so a card beat is seen, not only the
opening b-roll), sends them to Gemini in one request, and asks for a 0-10 score on
the rubric the 2026-11-17 panel named: sharpness, brightness, Thai text layout,
and whether it reads as the reference look (a designed card over real footage).

    python3 scripts/grade_video_vision.py --video work/qa_demo/video.mp4
    python3 scripts/grade_video_vision.py --video v.mp4 --frames 6 --json
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gemini_text  # noqa: E402

# gemini-3.5-flash-lite intermittently 503s under load; 3.1 answered live 2026-11-19.
MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite-latest")

RUBRIC = (
    "คุณคือผู้ตรวจคุณภาพวิดีโอการศึกษาไทย ดูเฟรมที่สุ่มมาจากวิดีโอเดียว แล้วให้คะแนนรวม 0-10 "
    "โดยประเมิน 4 ด้าน: (1) ความคมชัด (2) ความสว่าง (3) การจัดวางข้อความไทย "
    "(4) ภาพรวมเทียบมาตรฐาน 'การ์ดดีไซน์วางบนฟุตเทจจริง' ภาพเคลื่อนไหวไม่มีพิธีกร. "
    "ตอบเป็น: คะแนนรวม X/10, จุดเด่น 1 ข้อ, จุดที่ควรแก้ 1 ข้อ, สรุป 'ผ่าน' หรือ 'ไม่ผ่าน' "
    "(ผ่าน = >=6/10). ห้ามอธิบายยาว"
)


def sample_frames(video: str, n: int, out_dir: str) -> list[str]:
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True, check=True).stdout.strip())
    paths = []
    for i in range(n):
        # spread across the middle 90% so the first/last frames (fades) are skipped
        t = dur * (0.05 + 0.9 * (i / max(n - 1, 1)))
        p = os.path.join(out_dir, f"frame_{i:02d}.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                        "-i", video, "-frames:v", "1", "-q:v", "3", p], check=True)
        paths.append(p)
    return paths


def ask(frames: list[str], key: str) -> str:
    parts = [{"text": RUBRIC}]
    for p in frames:
        b = base64.b64encode(open(p, "rb").read()).decode()
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2}}
    last = ""
    for model in MODELS:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
               f":generateContent?key={key}")
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as fh:
                data = json.load(fh)
            return f"[{model}]\n" + gemini_text.text_of(data)
        except urllib.error.HTTPError as exc:
            last = f"{model}: HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            last = f"{model}: {type(exc).__name__}: {exc}"
    raise RuntimeError(last)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY not set")
    with tempfile.TemporaryDirectory() as td:
        frames = sample_frames(a.video, a.frames, td)
        print(f"sampled {len(frames)} frames from {a.video}", file=sys.stderr)
        answer = ask(frames, key)
    if a.json:
        print(json.dumps({"video": a.video, "frames": a.frames, "grade": answer},
                         ensure_ascii=False))
    else:
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
