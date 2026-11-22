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
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(cmd: list) -> tuple:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def label_for_piece(stem: str) -> str:
    """A readable chapter label from a piece filename stem: `03_others` -> `others`."""
    import re as _re
    return _re.sub(r"^\d+[_\-]+", "", stem).replace("_", " ").strip() or stem


def build_chapter_plan(work: str, info_path: str, images_dir: str,
                       style: str = "knowledge", prompt: str = "",
                       max_cards: int = 24) -> str:
    """Write a chapters.json mapping each narration beat to its own illustration.

    The panel's verdict (2026-11-16) was that a moving gradient with captions
    alone still reads as low-effort; the picture must change as the narration
    moves between beats. `make_compilation` already records each piece's duration
    and the cycle count, so the same boundaries `make_chapter_video` uses give
    every beat a start/end. One illustration is generated per (coalesced) beat and
    named after the piece, so a rebuild reproduces the same art.

    Returns the path to the plan (consumed by make_kinetic_video --chapters).
    """
    import make_chapter_video as _mcv
    info = json.load(open(info_path, encoding="utf-8"))
    segs = _mcv.coalesce(_mcv.piece_boundaries(info), max_cards)
    if not segs:
        raise SystemExit(f"{info_path} has no pieces; cannot plan chapters")
    os.makedirs(images_dir, exist_ok=True)
    plan, t = [], 0.0
    for i, (name, dur) in enumerate(segs):
        stem = os.path.splitext(os.path.basename(name))[0]
        dst = os.path.join(images_dir, stem + ".jpg")
        if not os.path.exists(dst):
            seed = int(hashlib.sha256(stem.encode()).hexdigest()[:8], 16)
            subj = (prompt + ", " if prompt else "") + label_for_piece(stem)
            # The standard is a uniform photoreal set (the owner's reference look,
            # docs/QA-VIDEO-STANDARD.md). gen_cover_image falls back to a procedural
            # gradient when the free generator is rate-limited; a gradient chapter
            # dropped into a photoreal video reads as broken, so retry, then FAIL
            # rather than ship a mixed set. Never skip the chapter -- a generator
            # that can drop a piece must fail, not write a partial plan.
            for attempt in range(3):
                rc, log = run([sys.executable, os.path.join(HERE, "gen_cover_image.py"),
                               "--out", dst, "--style", style, "--seed", str(seed),
                               "--prompt", subj, "--width", "1280", "--height", "720"])
                if rc == 0 and os.path.exists(dst) and "procedural" not in log:
                    break
                if attempt < 2:
                    time.sleep(4)
            else:
                raise SystemExit(
                    f"no photoreal art for chapter {i + 1} ({stem}) after 3 tries; "
                    "refusing to ship a mixed still set -- rerun when the free "
                    "image generator is not rate-limited")
        plan.append({"image": dst, "start": round(t, 3),
                     "end": round(t + dur, 3), "label": label_for_piece(stem)})
        t += dur
    out = os.path.join(work, "chapters.json")
    json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"chapter plan: {len(plan)} illustrations -> {out}")
    return out


def build_broll_plan(work: str, info_path: str, max_cards: int = 24) -> str:
    """Write a broll.json mapping each narration beat to a REAL stock clip.

    The owner's reference is real live-action footage, and a free generative model
    cannot make a believable human (measured 2026-11-17), so the standard uses free
    licence-clean real video (fetch_broll.py -> Coverr). One clip is fetched per
    (coalesced) beat and named after the piece, so a rebuild reuses it. A beat that
    cannot be sourced FAILS the build rather than shipping a still into a live-action
    set -- a generator that can drop a piece must fail, not write a partial plan.

    Returns the path to the plan (consumed by make_kinetic_video --broll).
    """
    import make_chapter_video as _mcv
    import fetch_broll
    info = json.load(open(info_path, encoding="utf-8"))
    segs = _mcv.coalesce(_mcv.piece_boundaries(info), max_cards)
    if not segs:
        raise SystemExit(f"{info_path} has no pieces; cannot plan b-roll")
    clips_dir = os.path.join(work, "broll")
    os.makedirs(clips_dir, exist_ok=True)
    plan, t, used, credits = [], 0.0, set(), []
    for i, (name, dur) in enumerate(segs):
        stem = os.path.splitext(os.path.basename(name))[0]
        dst = os.path.join(clips_dir, stem + ".mp4")
        if not os.path.exists(dst):
            q = label_for_piece(stem)
            hit = fetch_broll.pick(q, avoid=used)
            if not hit or not fetch_broll.download(hit, dst):
                raise SystemExit(
                    f"no real b-roll for beat {i + 1} ({stem!r}) from Coverr; "
                    "refusing to ship a still into a live-action set -- rerun when "
                    "the keyless API answers")
            used.add(hit.get("id"))
            credits.append({"beat": stem, **fetch_broll.attribution(hit)})
        plan.append({"clip": dst, "start": round(t, 3),
                     "end": round(t + dur, 3), "label": label_for_piece(stem)})
        t += dur
    out = os.path.join(work, "broll.json")
    json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if credits:
        json.dump(credits, open(os.path.join(work, "broll_credits.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"b-roll plan: {len(plan)} clips -> {out}")
    return out


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
                    choices=["dharma", "family", "genx", "knowledge"],
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
    ap.add_argument("--bed-file", default=None,
                    help="real music to loop under the narration (e.g. a Flow "
                         "Music export); omit to pick a validator-passing bed from "
                         "assets/music -- never a synthesised drone")
    ap.add_argument("--bed-ledger", default=None,
                    help="JSON file recording which build used which bed, so two "
                         "videos do not share one")
    ap.add_argument("--key", default=None,
                    help="this build's identity for the bed ledger "
                         "(default: the content directory name)")
    ap.add_argument("--chapters", action="store_true",
                    help="change the picture per piece (one card per chapter) "
                         "instead of one card looping for the whole file")
    ap.add_argument("--broll", action="store_true",
                    help="use REAL stock footage (one clip per piece, via the free "
                         "keyless Coverr API) as the kinetic engine's base -- the "
                         "owner's reference look (docs/QA-VIDEO-STANDARD.md)")
    ap.add_argument("--engine", default="poster", choices=["poster", "kinetic"],
                    help="poster = the still card (legacy); kinetic = an "
                         "always-moving background with captions synced to the "
                         "narration (the ch4 pivot, see make_kinetic_video.py)")
    ap.add_argument("--channel", default="dharma",
                    help="channel the build is for (content ledger grouping)")
    ap.add_argument("--brand", default="PCSEV",
                    help="persistent corner tag for the kinetic engine")
    a = ap.parse_args()

    # The cold open decides the first two minutes, so it may come from a file that
    # lives in the repo (reviewable, reusable) rather than a one-line argument.
    hook_text = a.hook
    if a.hook_file and os.path.exists(a.hook_file):
        hook_text = open(a.hook_file, encoding="utf-8").read().strip()
    elif a.hook_file:
        print(f"hook file {a.hook_file} not found; using --hook", file=sys.stderr)

    # K's rule (2026-11-22): the STORY must be new too, not just the picture. A
    # part that already aired in another video makes this build fail, before any
    # render time is spent.
    import content_ledger as _cl
    ledger_key = a.key or os.path.basename(os.path.normpath(a.content))
    story_parts = _cl.parts_of(a.content)
    aired = _cl.used_parts(_cl.load(), ledger_key)
    clash = {p["id"]: aired[p["sha256"]] for p in story_parts if p["sha256"] in aired}
    if clash:
        print(f"FAIL: these parts already aired in another video: {clash}",
              file=sys.stderr)
        return 3

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
                   *(["--hook", hook_text] if hook_text else []),
                   *(["--bed-file", a.bed_file] if a.bed_file else []),
                   *(["--bed-ledger", a.bed_ledger] if a.bed_ledger else []),
                   *(["--timing"] if a.engine == "kinetic" else []),
                   "--key", a.key or os.path.basename(a.content)]),
    ]

    def video_step() -> tuple:
        """The video command, resolved AFTER the audio step.

        The kinetic-chapters plan needs the audio's own `info.json` (piece
        durations and cycle count) to place each illustration at the right beat,
        and that file does not exist until the audio step has run -- so this is
        built lazily, not when `steps` is assembled (measured 2026-11-16: the
        eager version printed "no audio info.json; skipping per-chapter art" and
        shipped the plain gradient).
        """
        if a.engine == "kinetic":
            # The ch4 pivot: a picture that moves the whole time, with captions
            # timed to the narration, instead of one still card. With --chapters
            # each beat ALSO gets its own illustration over the moving base (the
            # panel's 2026-11-16 verdict: a moving gradient alone still reads as
            # low-effort). Without it the renderer is the plain moving base.
            chap_args = []
            if a.broll:
                info_path = mp3 + ".info.json"
                if os.path.exists(info_path):
                    plan = build_broll_plan(a.work, info_path)
                    chap_args = ["--broll", plan]
                else:
                    print("kinetic --broll: no audio info.json; skipping real "
                          "b-roll", file=sys.stderr)
            elif a.chapters:
                info_path = mp3 + ".info.json"
                if os.path.exists(info_path):
                    plan = build_chapter_plan(
                        a.work, info_path, os.path.join(a.work, "images"),
                        style=a.image_style, prompt=a.image_prompt)
                    chap_args = ["--chapters", plan]
                else:
                    print("kinetic --chapters: no audio info.json; skipping "
                          "per-chapter art", file=sys.stderr)
            return ("video", [sys.executable,
                              os.path.join(HERE, "make_kinetic_video.py"),
                              "--audio", mp3, "--timing", mp3 + ".timing.json",
                              "--out", mp4, "--title", a.title,
                              "--brand", a.brand, *chap_args])
        if a.chapters:
            return ("video", [sys.executable,
                              os.path.join(HERE, "make_chapter_video.py"),
                              "--audio", mp3, "--info", mp3 + ".info.json",
                              "--images", images_dir, "--out", mp4,
                              "--title", a.title, "--subtitle", a.subtitle,
                              "--style", a.image_style,
                              "--prompt", a.image_prompt])
        return ("cover", [sys.executable, "-c",
                          f"import sys;sys.path.insert(0,{HERE!r});import make_poster;"
                          f"make_poster.build({image!r},{cover!r},{a.title!r},"
                          f"{a.subtitle!r},3)"])

    def run_step(name: str, cmd: list) -> int:
        print(f"== {name} ==", flush=True)
        rc, log = run(cmd)
        sys.stdout.write(log[-2000:])
        if rc != 0:
            print(f"build failed at step '{name}' (exit {rc})", file=sys.stderr)
        return rc

    # Audio first, always: the kinetic plan depends on the audio's own info.json.
    if run_step(*steps[0]) != 0:
        return 2
    if not a.skip_video:
        if run_step(*video_step()) != 0:
            return 2
        # The legacy poster path needs a cover before the video; its video_step
        # returned the cover step, so run the actual poster video now.
        if a.engine != "kinetic" and not a.chapters:
            if run_step("video", [sys.executable,
                                  os.path.join(HERE, "make_night_video.py"),
                                  "--audio", mp3, "--image", image, "--cover", cover,
                                  "--out", mp4, "--loop-seconds",
                                  str(a.loop_seconds)]) != 0:
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
    if rc == 0:
        _cl.stamp(ledger_key, a.channel, story_parts, title=a.title,
                  music=a.bed_file or "")
        print(f"content stamped: {ledger_key} ({len(story_parts)} parts)")
    print(json.dumps({"verdict": verdict}, ensure_ascii=False))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
