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


def label_for_piece(stem: str) -> str:
    """A readable chapter label from a piece filename stem: `03_others` -> `others`."""
    import re as _re
    return _re.sub(r"^\d+[_\-]+", "", stem).replace("_", " ").strip() or stem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--content", required=True, help="directory of numbered .txt pieces")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", help="where the mp4/mp3 land (default: --work)")
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--image", default=None,
                    help="cover source image; omit to generate a unique one")
    ap.add_argument("--image-prompt", default="",
                    help="subject for the generated cover (English, no text)")
    ap.add_argument("--image-style", default="dharma",
                    choices=["dharma", "family"],
                    help="house style for the generated cover")
    ap.add_argument("--loop-seconds", type=float, default=24.0)
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--title", default="หลับถึงเช้า", help="poster title")
    ap.add_argument("--subtitle", default="ธรรมะก่อนนอน เปิดทิ้งไว้ทั้งคืน",
                    help="poster subtitle")
    ap.add_argument("--voice", default=None, help="edge-tts voice (default: dharma's)")
    ap.add_argument("--hook", default="",
                    help="one-line opening hook spoken before the body")
    ap.add_argument("--hook-file", default="",
                    help="file holding the spoken cold open (several lines); "
                         "overrides --hook. Kept in the repo so the opening can be "
                         "reviewed and reused, not buried in a workflow string.")
    ap.add_argument("--chapters", action="store_true",
                    help="change the picture per piece (one card per chapter) "
                         "instead of one card looping for the whole file")
    a = ap.parse_args()

    # The cold open decides the first two minutes, so it may come from a file that
    # lives in the repo (reviewable, reusable) rather than a one-line argument.
    hook_text = a.hook
    if a.hook_file and os.path.exists(a.hook_file):
        hook_text = open(a.hook_file, encoding="utf-8").read().strip()
    elif a.hook_file:
        print(f"hook file {a.hook_file} not found; using --hook", file=sys.stderr)

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

    # K's rule: no two videos share an image. Generate one per build unless the
    # caller passed --image. The seed is derived from the content directory name,
    # so a rebuild of the same set yields the same picture (the ledger stays
    # meaningful) while a different set yields a different one.
    def gen_image(dst: str, seed: int, prompt: str) -> int:
        rc, log = run([sys.executable, os.path.join(HERE, "gen_cover_image.py"),
                       "--out", dst, "--style", a.image_style,
                       "--seed", str(seed), "--prompt", prompt])
        sys.stdout.write(log)
        return rc

    import hashlib as _h
    base_seed = int(_h.sha256(os.path.basename(os.path.normpath(a.content))
                              .encode()).hexdigest()[:8], 16)

    image = a.image
    if not image:
        image = os.path.join(a.work, "source.jpg")
        if gen_image(image, base_seed, a.image_prompt) != 0:
            print("could not generate a cover image", file=sys.stderr)
            return 2

    # In chapter mode each piece gets its own card, so the screen changes as the
    # narration moves to the next beat. The seed varies per piece but stays tied
    # to the piece name, so a rebuild reproduces the same set.
    images_dir = os.path.join(a.work, "images")
    if a.chapters and not a.skip_video:
        os.makedirs(images_dir, exist_ok=True)
        for i, fn in enumerate(parts):
            stem = os.path.splitext(fn)[0]
            dst = os.path.join(images_dir, stem + ".jpg")
            if os.path.exists(dst):
                continue
            seed = (base_seed + int(_h.sha256(stem.encode()).hexdigest()[:6], 16)) % (2 ** 31)
            prompt = (a.image_prompt or "") + f", mood of {label_for_piece(stem)}"
            if gen_image(dst, seed, prompt) != 0:
                print(f"could not generate art for {fn}; falling back to the cover",
                      file=sys.stderr)
        # The hook card shares the first piece's art; the renderer names it 00_hook.
        if hook_text:
            first = os.path.join(images_dir, os.path.splitext(parts[0])[0] + ".jpg")
            if os.path.exists(first):
                import shutil as _sh
                _sh.copyfile(first, os.path.join(images_dir, "00_hook.jpg"))

    steps = [
        ("audio", [sys.executable, os.path.join(HERE, "make_compilation.py"),
                   "--out", mp3, "--part",
                   os.path.join(a.content, "[0-9]*.txt"),
                   "--work", a.work, "--minutes", str(a.minutes),
                   "--voice", a.voice or "th-TH-NiwatNeural",
                   *(["--hook", hook_text] if hook_text else [])]),
    ]
    if not a.skip_video:
        if a.chapters:
            steps += [("video", [sys.executable,
                                 os.path.join(HERE, "make_chapter_video.py"),
                                 "--audio", mp3, "--info", mp3 + ".info.json",
                                 "--images", images_dir, "--out", mp4,
                                 "--title", a.title, "--subtitle", a.subtitle,
                                 "--style", a.image_style,
                                 "--prompt", a.image_prompt])]
        else:
            steps += [
                ("cover", [sys.executable, "-c",
                           f"import sys;sys.path.insert(0,{HERE!r});import make_poster;"
                           f"make_poster.build({image!r},{cover!r},{a.title!r},"
                           f"{a.subtitle!r},3)"]),
                ("video", [sys.executable, os.path.join(HERE, "make_night_video.py"),
                           "--audio", mp3, "--image", image, "--cover", cover,
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
