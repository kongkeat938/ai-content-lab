#!/usr/bin/env python3
"""Turn one episode spec into ONE clip at the quality K approved -- repeatably.

K, 2026-11-20: the approved demo becomes the standard, and the job now is to make
clip creation give that quality **every time** (คุณภาพขั้นต่ำต้องแบบนี้ / นิ่ง).
Two things stood in the way, both measured:

  1. `ai_scene.py` called the sampler with **no seed**, so the same prompt produced a
     different picture on every run. An approved clip could therefore never be
     rebuilt -- every re-render was a new, unreviewed video. Fixed there (--seed).
  2. The demo's build lived in `/tmp/demo1/build_multi.sh`, which the pod deletes.
     So the look that was approved existed only as one file, not as a step anyone
     could repeat. This file is that step, in the repo.

What it does, in order, and why each part is not optional:

  * refuses while `content/STOP` exists (K's stop order covers building, not just
    uploading);
  * takes its pictures from the vault and **stamps each one as banned** -- the rule
    that no two clips may share a picture, on any channel (rule 6);
  * renders every beat with the ONE approved look (`video_grade.GRADE`, 1.06 lanczos
    push) and joins the beats with crossfades, the way the demo was cut;
  * lays Thai narration (edge-tts via `make_audio`) and AI music under it, mastered
    to -14 LUFS by the existing two-pass normaliser;
  * runs `clip_standard.verify_clip` on the finished file and **holds** it (writes
    nothing to the queue) when it does not meet the floor.

It does NOT upload. The queue is `assets/queue/` (rule 3) and K decides what leaves it.

Usage:
    python3 scripts/render_clip.py --spec episode.json --out assets/queue/<name>.mp4
    python3 scripts/render_clip.py --spec episode.json --dry-run   # plan only
"""
from __future__ import annotations

import argparse
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

import clip_standard  # noqa: E402
import image_vault  # noqa: E402
import kill_switch  # noqa: E402
import video_grade  # noqa: E402

W, H, FPS = video_grade.W, video_grade.H, video_grade.FPS
QUEUE = os.path.join(ROOT, "assets", "queue")
XFADE = 0.6           # seconds of crossfade between beats
BEAT_MIN = 3.0        # a beat shorter than this cannot hold a sentence

# Narration defaults: the house voice `make_audio` ships (its argparse defaults),
# repeated here so a clip is reproducible from the spec alone.
VOICE = "th-TH-NiwatNeural"
RATE = "-12%"
PITCH = "-10Hz"

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
       "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-color_range", "tv", "-colorspace", "bt709",
       "-color_primaries", "bt709", "-color_trc", "bt709",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def sh(cmd: list, timeout: int = 1800) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=timeout)
    if r.returncode != 0:
        sys.stderr.write("command failed: " + " ".join(cmd)[:400] + "\n")
        sys.stderr.write(r.stderr[-2500:] + "\n")
        raise RuntimeError("ffmpeg failed")


def voice_key(text: str, voice: str = VOICE, rate: str = RATE,
              pitch: str = PITCH) -> str:
    return hashlib.sha256(f"{voice}|{rate}|{pitch}|{text}".encode()).hexdigest()[:24]


def cached_voice(text: str, out: str, work: str) -> str:
    """One narration file per (text, voice, rate, pitch) -- cached forever after.

    Measured 2026-11-20: edge_tts is NOT deterministic. The same Thai sentence
    returned PCM that differed on 33% of samples (max 2381), so a re-render of an
    approved clip produced a different voice track and a different video file. The
    picture was already reproducible (same md5); the voice was the remaining drift.
    Caching by content turns the network synthesis into a one-time cost and makes
    every later render byte-identical.
    """
    cache_dir = os.environ.get("VOICE_CACHE_DIR") or os.path.join(
        ROOT, "assets", "voice_cache")
    os.makedirs(cache_dir, exist_ok=True)
    key = voice_key(text)
    keep = os.path.join(cache_dir, key + ".mp3")
    if not os.path.exists(keep):
        script = os.path.join(work, f"{key}.txt")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(text.strip() + "\n")
        tmp = os.path.join(work, key + ".raw.mp3")
        import make_audio
        make_audio.build(script, tmp, VOICE, RATE, PITCH, 0.35)
        # /tmp is a different filesystem from the workspace, so a rename fails with
        # EXDEV; copying is the portable move (and the cache stays atomic because
        # only a complete file ever reaches `keep`).
        shutil.copyfile(tmp, keep + ".part")
        os.replace(keep + ".part", keep)
        print(f"  voice cached {key} ({len(text)} chars)", flush=True)
    shutil.copyfile(keep, out)
    return out


def dur(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return float(r.stdout.strip())


def load_spec(path: str) -> dict:
    """Validate the spec up front. A spec that can drop a beat must fail here.

    A generator that silently skips a piece is the defect this repo keeps hitting,
    so every beat is checked before any encoding starts -- a missing picture or an
    empty line stops the run instead of shipping a short clip.
    """
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    beats = spec.get("beats") or []
    if not beats:
        raise SystemExit(f"spec {path}: no beats")
    for i, b in enumerate(beats, 1):
        if not b.get("image"):
            raise SystemExit(f"spec {path}: beat {i} has no image")
        if not os.path.exists(b["image"]):
            raise SystemExit(f"spec {path}: beat {i} image missing: {b['image']}")
        if not (b.get("text") or "").strip():
            raise SystemExit(f"spec {path}: beat {i} has no narration text")
    if not spec.get("title"):
        raise SystemExit(f"spec {path}: no title")
    return spec


def claim_pictures(spec: dict, vault: str) -> None:
    """Ban every picture this clip takes, before a single frame is encoded.

    Stamping first is deliberate: if the same picture is offered to a second clip
    while this one is still rendering, the second clip must lose, not this one.
    """
    channel = spec.get("channel") or "unassigned"
    clip = spec["id"]
    for i, b in enumerate(spec["beats"], 1):
        md5 = image_vault.claim_file(b["image"], channel, clip, vault)
        b["md5"] = md5
        print(f"  beat {i}: picture {md5[:8]} banned for {channel}/{clip}", flush=True)


def render_beat(img: str, aud: str, out: str, seconds: float) -> None:
    """One beat: the approved push on the still, the narration under it.

    The chain is `video_grade`'s, not a local copy -- measured 2026-11-17, a
    second copy of the look drifted 3x softer within a week.
    """
    frames = max(1, int(round(seconds * FPS)))
    # A slow push of ~4% over the beat: enough that no frame repeats, small enough
    # that the 1080p still is not resampled away.
    zoom = f"1.0+0.04*on/{frames}"
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={W}:{H},"
          f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d=1:s={W}x{H}:fps={FPS},"
          f"{video_grade.GRADE},setsar=1,format=yuv420p")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", f"{seconds:.3f}",
        "-i", img, "-i", aud,
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "1:a",
        *ENC, "-shortest", out])


def concat_xfade(parts: list, out: str, xf: float = XFADE) -> None:
    """Crossfade the beats, video and audio together, as the approved demo was cut.

    Measured 2026-11-20: a hard-cut shot detector finds NO cut in the approved demo
    (largest frame diff 5.49), because it crossfades. So the join is part of the
    look, not a detail -- hard cuts would also make the clip read as assembled.
    """
    if len(parts) == 1:
        shutil.copyfile(parts[0], out)
        return
    ds = [dur(p) for p in parts]
    inputs: list = []
    for p in parts:
        inputs += ["-i", p]
    fc, off = [], max(0.0, ds[0] - xf)
    vprev = "[0:v]"
    for i in range(1, len(parts)):
        lbl = f"[vx{i}]"
        fc.append(f"{vprev}[{i}:v]xfade=transition=fade:duration={xf}:"
                  f"offset={off:.3f}{lbl}")
        vprev = lbl
        off += max(0.0, ds[i] - xf)
    aprev = "[0:a]"
    for i in range(1, len(parts)):
        lbl = f"[ax{i}]"
        fc.append(f"{aprev}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri{lbl}")
        aprev = lbl
    sh(["ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(fc), "-map", vprev, "-map", aprev,
        *ENC, "-movflags", "+faststart", out])


def mix_audio(voice: str, music: str, out: str, music_db: float = -20.0) -> str:
    """Narration on top, music well under it, then the existing 2-pass master."""
    if music and os.path.exists(music):
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-i", music,
            "-filter_complex",
            f"[1:a]volume={music_db}dB,aloop=loop=-1:size=2e9[bed];"
            f"[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "[a]", "-ar", "48000", "-ac", "2", out])
    else:
        shutil.copyfile(voice, out)
    import make_audio
    master = out.replace(".wav", ".master.wav")
    make_audio.loudnorm2(out, master)
    return master


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default=None,
                    help="where to write the clip (default assets/queue/<id>.mp4)")
    ap.add_argument("--vault", default=None)
    ap.add_argument("--music", default=None,
                    help="AI music file (scripts/ai_music.py output); optional")
    ap.add_argument("--voice", default=None,
                    help="reuse a narration file instead of synthesising one")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if kill_switch.stopped():
        why = kill_switch.reason()
        print(f"STOPPED: content/STOP exists -- nothing built. {why}", file=sys.stderr)
        return kill_switch.STOPPED_EXIT

    spec = load_spec(a.spec)
    out = a.out or os.path.join(QUEUE, f"{spec['id']}.mp4")
    vault = a.vault or image_vault.VAULT
    beats = spec["beats"]
    print(f"spec {spec['id']}: {len(beats)} beats, title {spec['title'][:50]!r}",
          flush=True)

    if a.dry_run:
        for i, b in enumerate(beats, 1):
            print(f"  beat {i}: {b['image']} :: {b['text'][:60]}")
        print(f"would write {out}")
        return 0

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    work = tempfile.mkdtemp(prefix="clip-")
    try:
        claim_pictures(spec, vault)

        import make_audio
        parts = []
        for i, b in enumerate(beats, 1):
            voice = os.path.join(work, f"v{i}.mp3")
            if a.voice and len(beats) == 1:
                shutil.copyfile(a.voice, voice)
            else:
                cached_voice(b["text"], voice, work)
            seconds = max(BEAT_MIN, dur(voice) + 0.4)
            part = os.path.join(work, f"b{i}.mp4")
            render_beat(b["image"], voice, part, seconds)
            parts.append(part)
            print(f"  beat {i}: {seconds:.1f}s rendered", flush=True)

        body = os.path.join(work, "body.mp4")
        concat_xfade(parts, body)
        voice = os.path.join(work, "voice.wav")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", body,
            "-vn", "-ar", "48000", "-ac", "2", voice])
        mastered = mix_audio(voice, a.music or "", os.path.join(work, "mix.wav"))
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", body, "-i", mastered,
            "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", "-movflags", "+faststart", out])

        ok, reasons, metrics = clip_standard.verify_clip(out)
        report = os.path.join(os.path.dirname(out) or ".",
                              os.path.basename(out) + ".standard.json")
        with open(report, "w", encoding="utf-8") as fh:
            json.dump({"id": spec["id"], "verdict": "pass" if ok else "fail",
                       "failures": reasons, "metrics": metrics,
                       "spec": os.path.abspath(a.spec)}, fh, indent=2)
        if not ok:
            held = out.replace(".mp4", ".held.mp4")
            os.replace(out, held)
            print("HELD (below the standard): " + "; ".join(reasons), file=sys.stderr)
            print(f"kept for inspection at {held}", file=sys.stderr)
            return 1
        print(f"PASS -> {out}", flush=True)
        print(json.dumps(metrics, indent=2), flush=True)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
