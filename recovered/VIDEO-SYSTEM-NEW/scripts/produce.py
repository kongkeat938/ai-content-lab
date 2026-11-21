#!/usr/bin/env python3
"""One story K wrote -> one finished clip, filed in the upload queue.

K owns the words; this rail owns the machinery. Every beat text is copied
verbatim from the story -- the rail never writes narration, so a clip can only
ever say what K approved.

What it does, in order:

  1. read the story and check it is complete (a story that would drop a beat fails);
  2. reserve one FREE picture per beat from the warehouse, all-or-nothing;
  3. render through `render_clip.py`, which rebuilds each picture from its recipe,
     so the pod having no files on disk is not a problem;
  4. verify against `clip_standard` and file the result in `assets/queue/index.json`;
  5. release the pictures again if the render never shipped -- a failed run must
     not burn stock for a clip that will never exist.

    python3 scripts/produce.py --story content/motion/01.json --channel dharma
    python3 scripts/produce.py --story content/motion/01.json --dry-run
    python3 scripts/produce.py --story a.json --story b.json --channel genx
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import clip_standard  # noqa: E402
import image_vault  # noqa: E402
import kill_switch  # noqa: E402

QUEUE = os.path.join(ROOT, "assets", "queue")
INDEX = os.path.join(QUEUE, "index.json")
RENDERER = os.path.join(HERE, "render_clip.py")
MUSIC_ROOT_HZ = (98.0, 110.0, 123.5)   # three beds, so two clips rarely share one


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def paused_channels() -> set:
    path = os.path.join(ROOT, "content", "PAUSED")
    try:
        with open(path, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def load_story(path: str) -> dict:
    """A story missing any piece is refused here, before a picture is reserved."""
    try:
        with open(path, encoding="utf-8") as fh:
            story = json.load(fh)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"{path}: unreadable story ({exc})") from exc
    if not str(story.get("id") or "").strip():
        raise SystemExit(f"{path}: no id")
    if not str(story.get("hook") or "").strip():
        raise SystemExit(f"{path}: no hook -- the first beat is the hook")
    lines = story.get("lines") or []
    if not lines:
        raise SystemExit(f"{path}: no lines -- a one-beat clip is a fragment, not a story")
    for i, line in enumerate(lines, 1):
        if not str(line).strip():
            raise SystemExit(f"{path}: line {i} is empty -- a dropped beat is a broken clip")
    return story


def beats_of(story: dict) -> list:
    """The narration, verbatim: hook first, then each line, then the call to action."""
    texts = [story["hook"], *story.get("lines", [])]
    cta = str(story.get("cta") or "").strip()
    if cta:
        texts.append(cta)
    return [{"text": str(t).strip()} for t in texts]


def title_of(story: dict) -> str:
    return str(story.get("title") or story["hook"]).strip()


def spec_for(story: dict, md5s: list, channel: str) -> dict:
    beats = beats_of(story)
    if len(md5s) != len(beats):
        raise SystemExit(f"story {story['id']}: {len(beats)} beats but {len(md5s)} pictures")
    return {"id": f"{channel}-{story['id']}", "channel": channel,
            "title": title_of(story),
            "mood": story.get("mood") or "",
            "genre": story.get("genre") or "",
            "beats": [dict(b, image_md5=m) for b, m in zip(beats, md5s)]}


def bed_for(clip_id: str, out: str) -> str:
    """A deterministic music bed, so the clip rebuilds the same way every time.

    `ai_music.py` needs torch, which this pod does not have (measured 2026-11-20),
    while `make_bed.py` synthesises a seamless ambient bed from first principles
    with no model. Rule 4 asks for AI music; until torch is installed this is the
    bed that actually exists, and it is deterministic by construction.
    """
    root = MUSIC_ROOT_HZ[int(hashlib.md5(clip_id.encode()).hexdigest()[:8], 16)
                         % len(MUSIC_ROOT_HZ)]
    rc = subprocess.call([sys.executable, os.path.join(HERE, "make_bed.py"),
                          "--out", out, "--seconds", "60", "--root", f"{root}"],
                         env=dict(os.environ, CONTENT_STOP_PATH="/tmp/no-stop-bed"))
    return out if rc == 0 and os.path.exists(out) else ""


def queue_add(entry: dict) -> None:
    """File one finished clip in the queue index, under the house lock.

    One index, not one file per clip: the posting system must be able to read the
    whole queue in one read, and two rails appending at once must not lose an entry.
    """
    import make_short as MS

    os.makedirs(QUEUE, exist_ok=True)
    with MS.ledger_lock(INDEX):
        data = {"videos": []}
        if os.path.exists(INDEX):
            try:
                with open(INDEX, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError) as exc:
                raise SystemExit(f"{INDEX} is unreadable ({exc}) -- refusing to "
                                 "overwrite a queue that may hold finished clips")
        data.setdefault("videos", [])
        for i, have in enumerate(data["videos"]):
            if have.get("id") == entry["id"]:
                data["videos"][i] = entry
                break
        else:
            data["videos"].append(entry)
        tmp = INDEX + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, INDEX)


def produce_one(story_path: str, channel: str, dry_run: bool,
                renderer: str, vault: str, music: bool) -> int:
    story = load_story(story_path)
    beats = beats_of(story)
    clip_id = f"{channel}-{story['id']}"
    data = image_vault.load(vault)
    free = len(image_vault.free_stock(data))
    print(f"{clip_id}: {len(beats)} beats, warehouse has {free} free picture(s)",
          flush=True)

    if dry_run:
        for i, b in enumerate(beats, 1):
            print(f"  beat {i}: {b['text'][:60]}")
        if free < len(beats):
            print(f"  SHORT: needs {len(beats)} pictures, has {free} -- this run "
                  "would refuse and burn nothing", flush=True)
        print(f"would write {os.path.join(QUEUE, clip_id + '.mp4')}")
        return 0

    try:
        md5s = image_vault.take_free(len(beats), channel, clip_id, vault)
    except RuntimeError as exc:
        print(f"REFUSED {clip_id}: {exc}", file=sys.stderr)
        print("stock the warehouse first: python3 scripts/generative_art.py "
              f"--count {len(beats)} --size 4096 --stock", file=sys.stderr)
        return 1
    print(f"  reserved {len(md5s)} picture(s): "
          + ", ".join(m[:8] for m in md5s), flush=True)

    out = os.path.join(QUEUE, f"{clip_id}.mp4")
    work = tempfile.mkdtemp(prefix=f"produce-{clip_id}-")
    shipped = False
    try:
        spec = spec_for(story, md5s, channel)
        spec_path = os.path.join(work, "spec.json")
        with open(spec_path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh, ensure_ascii=False, indent=1)

        cmd = [sys.executable, renderer, "--spec", spec_path, "--out", out,
               "--vault", vault]
        if music:
            bed = bed_for(clip_id, os.path.join(work, "bed.wav"))
            if bed:
                cmd += ["--music", bed]
        print(f"  rendering: {' '.join(os.path.basename(c) for c in cmd[:1])} "
              f"-> {os.path.relpath(out, ROOT)}", flush=True)
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"FAILED {clip_id}: renderer exited {rc}", file=sys.stderr)
            return 1

        ok, reasons, metrics = clip_standard.verify_clip(out)
        if not ok:
            held = out.replace(".mp4", ".held.mp4")
            if os.path.exists(out):
                os.replace(out, held)
            print(f"HELD {clip_id}: " + "; ".join(reasons), file=sys.stderr)
            return 1
        shipped = True

        queue_add({"id": clip_id, "channel": channel, "story": os.path.abspath(story_path),
                   "story_id": story["id"], "title": title_of(story),
                   "file": os.path.relpath(out, ROOT),
                   "pictures": md5s, "music": bool(music),
                   "metrics": metrics, "state": "queued", "built_at": now()})
        print(f"QUEUED {clip_id} -> {os.path.relpath(out, ROOT)}  "
              f"({metrics.get('size')}, {metrics.get('lufs')} LUFS, "
              f"{metrics.get('shots')} shots)", flush=True)
        return 0
    finally:
        if not shipped:
            freed = image_vault.release(md5s, clip_id, vault)
            if freed:
                print(f"  released {freed} picture(s) back to stock", flush=True)
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    kill_switch.require_running("produce")
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", action="append", required=True,
                    help="a story JSON K wrote (repeat for several)")
    ap.add_argument("--channel", required=True)
    ap.add_argument("--vault", default=None)
    ap.add_argument("--renderer", default=RENDERER)
    ap.add_argument("--no-music", dest="music", action="store_false", default=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.channel in paused_channels():
        print(f"{a.channel} is paused (content/PAUSED); nothing produced")
        return 0

    vault = a.vault or image_vault.VAULT
    failed = 0
    for story in a.story:
        if produce_one(story, a.channel, a.dry_run, a.renderer, vault, a.music) != 0:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
