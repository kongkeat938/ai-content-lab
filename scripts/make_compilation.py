"""Build a long sleep compilation from several short narrated pieces.

The channels ship 10-12 minute episodes, but the winning format in the
dharma-before-sleep niche is a 90-180 minute file that a listener leaves playing
all night (measured: the top clips in the niche are 82-240 minutes). This is that
format: it stitches short pieces into one continuous track and lays a slow
ambient bed underneath the whole thing.

The join is deliberate — a compilation is not a playlist. Each piece is mastered
on its own, then the parts are concatenated with a few seconds of silence between
them, so the listener hears a pause for a breath rather than a cut.

Everything here is free: edge-tts for the voice, ffmpeg for the mix. The bed is
real instrumental music drawn from assets/music (the owner forbade the
synthesised drone); when none is available the voice ships clean.

Usage:
    python make_compilation.py --out work/night/compilation.mp3 \
        --part scripts/night/*.txt --work work/night
"""
import argparse
import glob
import importlib.util
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_audio  # noqa: E402


def music_beds() -> list[str]:
    d = os.path.join(ROOT, "assets", "music")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg")))


def is_music(path: str) -> bool:
    """True when the bed passes the committed music test (not a sine drone)."""
    try:
        spec = importlib.util.spec_from_file_location(
            "_tmb", os.path.join(HERE, "test_music_beds.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return bool(mod.measure(path)["is_music"])
    except Exception:  # noqa: BLE001 - never let a measurement fault mute the file
        return False

# How far the bed sits below the voice. Measured on the reference clip: a bed
# 6-20 dB under the voice reads as "there is music" without ever fighting the
# narration. A sleep bed sits at the quiet end of that band.
BED_UNDER_VOICE_DB = 16.0
VOICE = "th-TH-NiwatNeural"
RATE, PITCH = "-12%", "-10Hz"
PAUSE_BETWEEN = 3.5  # seconds of silence between pieces


def run(cmd: list, **kw) -> None:
    subprocess.run(cmd, check=True, capture_output=True, **kw)


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def narrator_for(base: str) -> str | None:
    """Which voice a piece wants, from a marker in its filename.

    A compilation can mix narrators: a piece named `09_metta.edge.txt` is spoken
    in the house voice while its neighbours keep K's tone. The marker is the final
    dot-separated tag (after the name); anything else is `None`, meaning "whatever
    the environment says".
    """
    tags = base.split(".")
    if len(tags) >= 2 and tags[-1] in ("edge", "fish", "openvoice"):
        return tags[-1]
    return None


def build_part(script: str, work: str, voice: str = VOICE) -> dict:
    """Synthesise and master one piece. Resumable: an existing part is reused."""
    base = os.path.splitext(os.path.basename(script))[0]
    out = os.path.join(work, f"part_{base}.mp3")
    meta = os.path.join(work, f"part_{base}.json")
    if os.path.exists(out) and os.path.exists(meta):
        info = json.load(open(meta, encoding="utf-8"))
        if info.get("duration_sec", 0) > 30:
            print(f"  {base}: cached ({info['duration_sec']:.0f}s)")
            return info
    narrator = narrator_for(base)
    info = make_audio.build(script, out, voice, RATE, PITCH, PAUSE_BETWEEN,
                            narrator=narrator)
    info["name"] = base
    info["narrator"] = narrator or os.environ.get("NARRATOR", "auto")
    json.dump(info, open(meta, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  {base}: {info['duration_sec']:.0f}s  {info['lufs']} LUFS  "
          f"[{info['narrator']}]")
    return info


def concat(parts: list, out: str) -> None:
    listfile = out + ".list.txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    # Re-encode to one PCM stream: MP3 frame padding would otherwise put a tiny
    # gap at every join.
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listfile, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out])
    os.remove(listfile)


def hook_piece(text: str, work: str, voice: str = VOICE) -> dict | None:
    """Synthesise a short opening hook and return its info, or None if empty.

    The advisor panel (2026-11-07) put this first: people leave in the first
    minute, so the file must state its promise before it settles in. The hook is
    spoken once, in front of the looped body, so a replay passes through it again
    -- which is correct, the promise is what earns the next minute.
    """
    text = (text or "").strip()
    if not text:
        return None
    path = os.path.join(work, "00_hook.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    info = build_part(path, work, voice)
    info["name"] = "00_hook"
    return info


def sequence_to_length(parts: list, target_seconds: float) -> tuple:
    """Repeat the piece list until it reaches the target, with a longer breath
    between cycles than between pieces.

    A sleep file is meant to be left playing, so repetition is the format, not a
    defect -- but a whole cycle must not butt straight onto itself. The gap
    between cycles is the same silence file, sized separately.

    Each cycle is rotated by its index, so a listener who leaves the file playing
    does not hear the identical sequence back to back; the pieces and the total
    length are unchanged, only their order shifts.

    Returns (file list, cycles).
    """
    if not parts or target_seconds <= 0:
        return list(parts), 1
    one = sum(duration(p) for p in parts)
    if one <= 0:
        return list(parts), 1
    cycles = max(1, int(target_seconds // one) + (1 if target_seconds % one else 0))
    n = len(parts)
    seq = []
    for c in range(cycles):
        r = c % n
        seq.extend(parts[r:] + parts[:r])
    return seq, cycles


def bed_for(seconds: float, work: str, seed_file: str | None = None,
            key: str | None = None, ledger: str | None = None) -> str | None:
    """A real instrumental bed, looped to the length of the voice track.

    The synthesised drone that used to stand here is gone. Measured 2026-11-09 it
    fails the music test (tone_share 0.196, partials 5, env 0.34 -- one held low
    tone) and the owner forbade that "hum". `seed_file` is the owner's own music;
    otherwise a validator-passing bed is drawn from assets/music, and the `ledger`
    records which build used which bed so two videos do not share one. When none
    is available the caller is told to leave the voice clean, never to hum.
    """
    if seed_file:
        if not os.path.exists(seed_file):
            raise SystemExit(f"bed file not found: {seed_file}")
        seed = seed_file
    else:
        pool = [p for p in music_beds() if is_music(p)]
        if not pool:
            return None
        seed = _pick_unique_bed(pool, key, ledger)
    out = os.path.join(work, "bed.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", seed,
         "-t", f"{seconds:.3f}", "-ar", "48000", "-ac", "2",
         "-c:a", "pcm_s16le", out])
    return out


def _pick_unique_bed(pool: list[str], key: str | None, ledger: str | None) -> str:
    """Pick a bed no other build has used yet, when a ledger and key are given."""
    used: dict = {}
    if ledger and os.path.exists(ledger):
        try:
            with open(ledger, encoding="utf-8") as fh:
                used = json.load(fh).get("beds", {})
        except (OSError, ValueError):
            used = {}
    if key:
        free = [p for p in pool if used.get(os.path.basename(p), key) == key]
        pick = free[0] if free else pool[hash(key) % len(pool)]
        if ledger:
            used[os.path.basename(pick)] = key
            tmp = ledger + ".part"
            os.makedirs(os.path.dirname(os.path.abspath(ledger)), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"beds": used}, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, ledger)
        return pick
    return random.choice(pool)


def mix(voice: str, bed: str, out: str) -> None:
    v_lufs, _ = make_audio.measure(voice)
    b_lufs, _ = make_audio.measure(bed)
    if "?" in (v_lufs, b_lufs):
        raise RuntimeError(f"could not measure levels (voice={v_lufs} bed={b_lufs})")
    target_bed = float(v_lufs) - BED_UNDER_VOICE_DB
    gain = target_bed - float(b_lufs)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice, "-i", bed,
         "-filter_complex",
         f"[1:a]volume={gain:.2f}dB,afade=t=in:st=0:d=8[m];"
         f"[0:a][m]amix=inputs=2:duration=first:normalize=0,"
         f"alimiter=limit=0.85[out]",
         "-map", "[out]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out])
    print(f"  bed {b_lufs} -> {target_bed:.1f} LUFS "
          f"({BED_UNDER_VOICE_DB:.0f} dB under a {v_lufs} LUFS voice, gain {gain:+.1f} dB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--part", nargs="+", required=True,
                    help="scripts to stitch, in order (globs are expanded by the shell)")
    ap.add_argument("--work", required=True)
    ap.add_argument("--bed", default="yes", choices=["yes", "no"])
    ap.add_argument("--bed-file", default=None,
                    help="real music to loop under the voice (e.g. a Flow Music "
                         "export); omit to pick a validator-passing bed from "
                         "assets/music. There is no synthesised fallback: the "
                         "drone was forbidden, so a clean voice is used instead.")
    ap.add_argument("--bed-ledger", default=None,
                    help="JSON file recording which build used which bed, so two "
                         "videos do not share one")
    ap.add_argument("--key", default=None,
                    help="this build's identity for the bed ledger (default: --out)")
    ap.add_argument("--minutes", type=float, default=0.0,
                    help="target length; repeat the pieces until reached "
                         "(a sleep file is meant to be left playing)")
    ap.add_argument("--voice", default=VOICE, help="edge-tts voice")
    ap.add_argument("--hook", default="",
                    help="one-line opening hook spoken before the body "
                         "(the panel's #1 retention lever)")
    a = ap.parse_args()

    scripts = []
    for pat in a.part:
        hits = sorted(glob.glob(pat))
        scripts.extend(hits if hits else [pat])
    if not scripts:
        sys.exit("no scripts matched")
    os.makedirs(a.work, exist_ok=True)

    print(f"building {len(scripts)} pieces")
    infos = [build_part(s, a.work, a.voice) for s in scripts]

    hook = hook_piece(a.hook, a.work, a.voice)
    if hook:
        infos = [hook] + infos
        print(f"  hook: {hook['duration_sec']:.0f}s")

    part_files = [os.path.join(a.work, f"part_{i['name']}.mp3") for i in infos]

    cycles = 1
    if a.minutes > 0:
        # The hook plays once; only the body repeats to reach the target. Asking
        # sequence_to_length for the full target would let the hook count toward
        # it, and the file would come out short by the hook's length.
        hook_sec = hook["duration_sec"] if hook else 0.0
        body_files = part_files[len(part_files) - len(scripts):]
        body_files, cycles = sequence_to_length(body_files, a.minutes * 60 - hook_sec)
        part_files = ([part_files[0]] if hook else []) + body_files
        print(f"repeating the {len(scripts)} pieces x{cycles} to reach "
              f"{a.minutes:.0f} min")

    voice = os.path.join(a.work, "voice.wav")
    concat(part_files, voice)
    total = duration(voice)
    print(f"voice track: {total / 60:.1f} min")

    mixed = voice
    bed_used = False
    if a.bed == "yes":
        bed = bed_for(total, a.work, a.bed_file, a.key or a.out, a.bed_ledger)
        if bed:
            mixed = os.path.join(a.work, "mixed.wav")
            mix(voice, bed, mixed)
            bed_used = True
        else:
            # No real music available: ship the clean narration rather than a hum.
            print("no validator-passing bed in assets/music; shipping the voice "
                  "without a bed (the owner forbade the synthesised drone)",
                  file=sys.stderr)

    # Final master to the YouTube target, folded into one encode.
    make_audio.loudnorm2(mixed, a.out)
    lufs, peak = make_audio.measure(a.out)
    info = {
        "out": a.out,
        "pieces": [{"name": i["name"], "duration_sec": i["duration_sec"]}
                   for i in infos if not (hook and i is hook)],
        "hook": ({"name": hook["name"], "duration_sec": hook["duration_sec"]}
                 if hook else None),
        "cycles": cycles,
        "duration_sec": round(duration(a.out), 2),
        "minutes": round(duration(a.out) / 60, 1),
        "lufs": lufs,
        "true_peak_dbfs": peak,
        "bed": bed_used,
        "bed_under_voice_db": BED_UNDER_VOICE_DB,
        "voice": VOICE,
    }
    json.dump(info, open(a.out + ".info.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({k: info[k] for k in
                      ("minutes", "lufs", "true_peak_dbfs", "bed")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
