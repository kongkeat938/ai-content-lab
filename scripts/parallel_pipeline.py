#!/usr/bin/env python3
"""Two independent systems joined by a handoff folder: art in, clips out.

K (2026-11-19): "ถ้าแยกระบบ สร้างภาพกับทำคลิปได้แยกงานทำคู่ขนานเลย". So the picture
side and the clip side no longer call each other:

    SYSTEM A  art     renders PNGs into an art pool (PC1 renders, or this pod)
    SYSTEM B  clips   claims a picture from the pool and builds a clip from it

They meet only at a directory on disk. A is never blocked by B and B never waits
on a render: a clip takes whatever piece is already in the pool, and the pool
grows underneath. Run both at once -- that is the point.

    python3 scripts/parallel_pipeline.py art   --pool work/pool --count 40
    python3 scripts/parallel_pipeline.py clips --pool work/pool --stories content/motion/*.json

Both write a receipt (JSON) so the work is countable, not asserted. `--pool` is
the ONLY shared state, which is what makes the two sides separable.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def art_system(pool: str, count: int, size: int, seed: int, jobs: int,
               receipt: str | None) -> int:
    """SYSTEM A -- render pictures into the pool. Knows nothing about clips."""
    os.makedirs(pool, exist_ok=True)
    before = len(glob.glob(os.path.join(pool, "*.png")))
    cmd = [sys.executable, os.path.join(HERE, "generative_art.py"),
           "--count", str(count), "--size", str(size), "--seed", str(seed),
           "--out-dir", pool, "--jobs", str(jobs), "--skip-existing"]
    t0 = time.time()
    rc = subprocess.call(cmd)
    after = len(glob.glob(os.path.join(pool, "*.png")))
    took = time.time() - t0
    made = after - before
    print(f"art: {made} new pictures in {took:.0f}s "
          f"({made / max(took, 1e-9) * 60:.2f} img/min), pool now {after}")
    if receipt:
        _write(receipt, {"system": "art", "at": _now(), "rc": rc, "pool": pool,
                         "before": before, "after": after, "new": made,
                         "seconds": round(took, 1),
                         "img_per_min": round(made / max(took, 1e-9) * 60, 2)})
    return rc


def clip_system(pool: str, stories: list[str], out_dir: str, library_url: str,
                ledger: str | None, music_dir: str | None, receipt: str | None,
                jobs: int) -> int:
    """SYSTEM B -- build clips from whatever is already in the pool.

    Runs `jobs` renders at once. Each render claims a DIFFERENT picture (the claim
    is the ledger write, which is atomic), so parallelism cannot hand two clips
    the same image -- the guard test proves that by running this for real.

    Nothing counts as built until it passes the house QC gate (K, 2026-11-19:
    "คลิปต้องผ่านระบบ qc ก่อนนะ"). A clip that misses the standard is reported as
    FAILED with its reasons, so a substandard file can never be mistaken for a
    finished one.
    """
    os.makedirs(out_dir, exist_ok=True)
    if not stories:
        print("clips: no stories given", file=sys.stderr)
        return 2

    bed_ledger = (os.path.join(os.path.dirname(os.path.abspath(out_dir)),
                               "bed_ledger.json") if music_dir else None)
    procs: list[tuple[str, subprocess.Popen]] = []
    pending = list(stories)
    done: list[dict] = []
    t0 = time.time()

    def launch(story: str) -> None:
        sid = json.load(open(story, encoding="utf-8"))["id"]
        d = os.path.join(out_dir, sid)
        os.makedirs(d, exist_ok=True)
        art = _claim(pool, sid, d, library_url, ledger)
        cmd = [sys.executable, os.path.join(HERE, "make_motion_short.py"),
               "--story", story, "--out-dir", out_dir]
        if art:
            cmd += ["--art", art]
        bed = _bed_for(music_dir, sid, story, bed_ledger)
        if bed:
            cmd += ["--music", bed]
        log = open(os.path.join(d, "render.log"), "w", encoding="utf-8")
        procs.append((sid, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)))
        print(f"clips: started {sid} (art={os.path.basename(art) if art else 'painted'})")

    while pending or procs:
        while pending and len(procs) < max(1, jobs):
            launch(pending.pop(0))
        still = []
        for sid, p in procs:
            if p.poll() is None:
                still.append((sid, p))
                continue
            out = os.path.join(out_dir, sid, f"motion_{sid}.mp4")
            thumb = os.path.join(out_dir, sid, f"motion_{sid}.jpg")
            ok_render = p.returncode == 0 and os.path.exists(out)
            qc = {"ok": False, "reasons": ["not rendered"]}
            if ok_render:
                if not os.path.exists(thumb):
                    _thumbnail(out, thumb, _hook_of(stories, sid))
                qc = _qc(out, thumb)
            ok = ok_render and qc["ok"]
            size = os.path.getsize(out) if os.path.exists(out) else 0
            verdict = "ok" if ok else "FAILED"
            print(f"clips: {sid} {verdict} rc={p.returncode} {size} bytes "
                  f"qc={'pass' if qc['ok'] else 'FAIL'}")
            for reason in qc.get("reasons", [])[:6]:
                print(f"    qc: {reason}")
            done.append({"id": sid, "ok": ok, "rc": p.returncode, "bytes": size,
                         "out": out if os.path.exists(out) else None,
                         "qc": qc})
        procs = still
        if procs:
            time.sleep(1.0)

    took = time.time() - t0
    good = [d for d in done if d["ok"]]
    print(f"clips: {len(good)}/{len(done)} passed QC in {took:.0f}s "
          f"({len(good) / max(took, 1e-9) * 60:.2f} clips/min)")
    if receipt:
        _write(receipt, {"system": "clips", "at": _now(), "pool": pool,
                         "out_dir": out_dir, "seconds": round(took, 1),
                         "built": len(good), "total": len(done),
                         "clips_per_min": round(len(good) / max(took, 1e-9) * 60, 2),
                         "items": done})
    return 0 if len(good) == len(done) else 1


def _qc(video: str, thumb: str) -> dict:
    """Run the house Short standard over one build; return its verdict.

    This is the SAME gate the publish rail uses (short_standard.verify_short), not
    a second opinion: a clip that would be held at upload is held here, where the
    fix is cheap.
    """
    import short_standard
    ok, reasons, metrics = short_standard.verify_short(video, thumb)
    return {"ok": ok, "reasons": reasons, "metrics": metrics}


def _hook_of(stories: list[str], sid: str) -> str:
    for s in stories:
        try:
            d = json.load(open(s, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if str(d.get("id")) == sid:
            return str(d.get("hook") or "")
    return ""


def _thumbnail(video: str, out: str, hook: str) -> None:
    """Make the 9:16 thumbnail the QC gate requires, from the clip's own frame.

    Without this every clip failed QC for a missing thumbnail, which is a gap in
    the clip system rather than a defect in the clip. One source for the look:
    make_short_thumbnail.py, the same builder the Shorts rail uses.
    """
    subprocess.call([sys.executable, os.path.join(HERE, "make_short_thumbnail.py"),
                     "--video", video, "--hook", hook, "--out", out])


def _bed_for(music_dir: str | None, sid: str, story: str,
             ledger: str | None) -> str | None:
    """One music bed for this clip, chosen so no two clips share a bed.

    Measured 2026-11-19 (K): the built clips had NO music at all -- the pipeline
    accepted `--music` but nothing ever passed it, so every clip shipped voice
    only. The selector is `publish_shorts.pick_bed` (mood-matched, ledger-guarded)
    so this rail and the upload rail cannot drift apart.
    """
    if not music_dir or not os.path.isdir(music_dir):
        return None
    try:
        import publish_shorts as PS
    except Exception:                                  # noqa: BLE001
        return None
    mood = None
    try:
        mood = json.load(open(story, encoding="utf-8")).get("mood")
    except (OSError, ValueError):
        pass
    try:
        return PS.pick_bed(music_dir, sid, mood, ledger)
    except Exception:                                  # noqa: BLE001
        return None


def _claim(pool: str, sid: str, d: str, library_url: str,
           ledger: str | None) -> str | None:
    """Take one picture out of the pool for `sid`; never the same one twice.

    The pool is read-only here: the piece is COPIED to <d>/art.jpg and recorded in
    the ledger. Copying (not moving) keeps A free to add more while B reads.

    The claim is a compare-and-swap on the ledger under an exclusive lock. Read
    then write is NOT enough once clips run in parallel: two workers read the
    same `used` map, both find piece 3 free, and both take it -- measured
    2026-11-19 in the guard test, 4 parallel clips from a 4-piece pool shared
    pictures until the lock went in.
    """
    import hashlib
    import shutil

    cache = os.path.join(d, "art.jpg")
    if os.path.exists(cache):
        return cache
    pieces = sorted(glob.glob(os.path.join(pool, "*.png")))
    if not pieces:
        if library_url:
            import make_short as MS
            return MS.library_art(d, sid, library_url, ledger)
        return None

    import make_short as MS

    with MS.ledger_lock(ledger):
        used: dict[str, str] = {}
        if ledger and os.path.exists(ledger):
            try:
                used = json.load(open(ledger, encoding="utf-8")).get("md5", {})
            except (OSError, ValueError):
                used = {}
        start = int(hashlib.sha256(sid.encode()).hexdigest()[:8], 16) % len(pieces)
        for bump in range(len(pieces)):
            src = pieces[(start + bump) % len(pieces)]
            md5 = hashlib.md5(open(src, "rb").read()).hexdigest()
            if used.get(md5, sid) != sid:
                continue
            os.makedirs(d, exist_ok=True)
            shutil.copyfile(src, cache)
            if ledger:
                used[md5] = sid
                _write(ledger, {"md5": used})
            return cache
        return None


def _write(path: str, obj: dict) -> None:
    """Atomic write with a PER-PROCESS temp name.

    A shared `path + ".part"` is itself a race: two claimers write the same temp
    file and one `os.replace` finds it already moved (measured 2026-11-19, the
    guard's unlocked case died with FileNotFoundError on the .part file). The pid
    in the name keeps each writer's temp private.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("art", help="SYSTEM A: render pictures into the pool")
    a.add_argument("--pool", required=True)
    a.add_argument("--count", type=int, default=40)
    a.add_argument("--size", type=int, default=2048)
    a.add_argument("--seed", type=int, default=7000)
    a.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a.add_argument("--receipt", default=None)

    c = sub.add_parser("clips", help="SYSTEM B: build clips from the pool")
    c.add_argument("--pool", required=True)
    c.add_argument("--stories", nargs="+", required=True)
    c.add_argument("--out-dir", default=os.path.join(ROOT, "work", "motion_par"))
    c.add_argument("--library-url", default=os.environ.get("ART_LIBRARY_URL", ""))
    c.add_argument("--ledger", default=os.path.join(ROOT, "content",
                                                    "art_ledger_motion.json"))
    c.add_argument("--music-dir",
                   default=os.path.join(ROOT, "assets", "music"),
                   help="folder of CC0 beds; one per clip, never shared")
    c.add_argument("--jobs", type=int, default=2,
                   help="how many clips render at once")
    c.add_argument("--receipt", default=None)

    args = ap.parse_args()
    if args.cmd == "art":
        return art_system(args.pool, args.count, args.size, args.seed,
                          args.jobs, args.receipt)
    return clip_system(args.pool, args.stories, args.out_dir, args.library_url,
                       args.ledger, args.music_dir, args.receipt, args.jobs)


if __name__ == "__main__":
    sys.exit(main())
