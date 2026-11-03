#!/usr/bin/env python3
"""Build one night compilation end to end, and refuse to pass a bad one.

The three rail scripts (make_compilation, make_night_video, verify_night) each
do one job and exit 0 whether or not the result is good. Chaining them by hand
means the last command's exit code decides whether CI goes green -- so a build
whose true peak is over the gate still "passes" if nobody reads the log. This is
the one entrypoint a workflow calls: it runs the steps in order and makes the
verifier's verdict the process verdict.

    python3 scripts/build_night.py --content content/night_dharma_01 \
        --work work/night_dharma_01 --minutes 120 --out work/night_dharma_01

Exit codes: 0 = built and verified, 1 = verify failed, 2 = build failed.
Writes <out>/receipt.json with the measured numbers, so a caller reports
evidence instead of an assurance.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(cmd: list) -> tuple:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--content", required=True, help="directory of numbered .txt pieces")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", help="where the mp4/mp3 land (default: --work)")
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--image", default=os.path.join(ROOT, "assets", "images", "img00_00.jpg"),
                    help="cover source image")
    ap.add_argument("--loop-seconds", type=float, default=24.0)
    ap.add_argument("--skip-video", action="store_true")
    a = ap.parse_args()

    out = a.out or a.work
    os.makedirs(a.work, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    parts = sorted(f for f in os.listdir(a.content) if f.endswith(".txt"))
    if not parts:
        print(f"no .txt pieces in {a.content}", file=sys.stderr)
        return 2

    mp3 = os.path.join(out, "compilation.mp3")
    mp4 = os.path.join(out, "video.mp4")
    cover = os.path.join(out, "cover.jpg")

    steps = [
        ("audio", [sys.executable, os.path.join(HERE, "make_compilation.py"),
                   "--out", mp3, "--part",
                   os.path.join(a.content, "[0-9]*.txt"),
                   "--work", a.work, "--minutes", str(a.minutes)]),
    ]
    if not a.skip_video:
        steps += [
            ("cover", [sys.executable, "-c",
                       f"import sys;sys.path.insert(0,{HERE!r});import make_poster;"
                       f"make_poster.build({a.image!r},{cover!r},'หลับถึงเช้า',"
                       f"'ธรรมะก่อนนอน เปิดทิ้งไว้ทั้งคืน',3)"]),
            ("video", [sys.executable, os.path.join(HERE, "make_night_video.py"),
                       "--audio", mp3, "--image", a.image, "--cover", cover,
                       "--out", mp4, "--loop-seconds", str(a.loop_seconds)]),
        ]

    for name, cmd in steps:
        print(f"== {name} ==", flush=True)
        rc, log = run(cmd)
        sys.stdout.write(log[-2000:])
        if rc != 0:
            print(f"build failed at step '{name}' (exit {rc})", file=sys.stderr)
            return 2

    if a.skip_video:
        print("video skipped; nothing to verify")
        return 0

    print("== verify ==", flush=True)
    rc, log = run([sys.executable, os.path.join(HERE, "verify_night.py"), mp4])
    sys.stdout.write(log)
    verdict = "pass" if rc == 0 else "fail"

    receipt = {
        "content": a.content,
        "pieces": parts,
        "minutes_target": a.minutes,
        "audio": mp3,
        "video": mp4,
        "verdict": verdict,
        "verify_log": log.strip().splitlines(),
    }
    info = os.path.join(a.work, "compilation.mp3.info.json")
    if os.path.exists(info):
        receipt["audio_info"] = json.load(open(info, encoding="utf-8"))
    vin = mp4 + ".info.json"
    if os.path.exists(vin):
        receipt["video_info"] = json.load(open(vin, encoding="utf-8"))
    json.dump(receipt, open(os.path.join(out, "receipt.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({"verdict": verdict}, ensure_ascii=False))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
