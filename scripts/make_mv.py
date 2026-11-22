"""Build a music video: fresh AI images + a music bed, stamped in one ledger.

The owner's rule (K, 2026-11-22): every MV gets NEW images -- never an image
that another MV already used -- and each image must be stamped with the MV that
owns it. So the ledger is written before the video is assembled, and an image
whose sha256 is already claimed makes the run FAIL instead of being reused.

Usage:
    python make_mv.py --mv-id mv_2026-11-22_01 --style dharma \
        --title "เพลงธรรมะบรรเลง 1 ชั่วโมง" --minutes 60 \
        --music assets/music/bed-calm-....mp3 --out work/mv/mv_2026-11-22_01.mp4
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_cover_image  # noqa: E402

W, H = 1920, 1080
FPS = 25
SEG_SEC = 25.0
TP_CEILING = -3.0
TP_MARGIN = 0.1
LUFS_MIN, LUFS_MAX = -15.0, -13.0
LEDGER = os.path.join(ROOT, "content", "art_ledger_mv.json")

# One scene per image. A prompt carries the MV's own theme, so two MVs that
# share a style still ask for different pictures; the sha256 check is what
# actually guarantees no repeat.
SCENES = {
    "dharma": [
        "a Thai temple at first light, golden roof, mist over the courtyard",
        "a lone monk walking a forest path at dawn, saffron robe",
        "a lotus pond in front of an old ordination hall",
        "a single candle burning beside a Buddha statue, dark room",
        "rain falling on the terracotta roof of a temple pavilion",
        "incense smoke curling in a beam of morning light",
        "a moonlit stupa reflected in still water",
        "a misty forest temple in the mountains at sunrise",
        "a wooden bridge over a canal at dusk, warm lanterns",
        "a stone Buddha covered in fallen leaves",
        "prayer flags moving in a light breeze under a clear sky",
        "a quiet meditation hall, open windows, soft daylight",
    ],
    "genx": [
        "a cup of tea on a windowsill at sunrise, quiet street outside",
        "an empty chair by a window with soft afternoon light",
        "a desk with an open notebook and a warm lamp at night",
        "rain on a cafe window, a single table, muted colours",
        "a park bench under autumn trees, early morning light",
        "a small balcony with plants at golden hour",
        "a path through tall grass under a pale evening sky",
        "a train window view of fields at dusk",
        "a bookshelf with a reading lamp, calm evening",
        "a kitchen table with a bowl of fruit in morning light",
        "a lake at dawn with a wooden pier",
        "a quiet rooftop looking over a sleeping city at dawn",
    ],
    "knowledge": [
        "a glass prism splitting sunlight into a rainbow on a table",
        "a clear glass of water with a pencil, light bending",
        "a paper boat floating in a bowl of water",
        "soap bubbles catching light in a garden",
        "a magnet with iron filings on white paper",
        "a small plant growing toward a window",
        "a thermometer and a glass of ice water on a table",
        "a telescope pointed at a clear night sky",
        "a stack of books with a magnifying glass",
        "a balloon tied to a string against a blue sky",
        "rain drops on a leaf, close up",
        "a simple circuit with a light bulb glowing",
    ],
}


# A visual story per MV. K's rule covers the CONTENT too: a follower who watches
# every clip must see something new, so two MVs never share an arc (nor a music
# bed) on the same channel.
ARCS = {
    "dawn-flow": {"pals": ["sand", "ember"], "gens": ["flow", "contour", "moire"]},
    "water-glass": {"pals": ["teal", "midnight"], "gens": ["truchet", "voronoi", "moire"]},
    "forest-lines": {"pals": ["sage", "teal"], "gens": ["contour", "dgrowth", "voronoi"]},
    "night-orbit": {"pals": ["midnight", "violet"], "gens": ["attractor", "harmonograph", "superformula"]},
    "ember-reaction": {"pals": ["ember", "rose"], "gens": ["reaction", "dgrowth", "flow"]},
    "ink-mandala": {"pals": ["ink", "violet"], "gens": ["superformula", "harmonograph", "truchet"]},
}

PALETTES = {
    "dharma": ["midnight", "ink", "violet", "teal"],
    "genx": ["sand", "sage", "ember", "ink"],
    "knowledge": ["teal", "sand", "violet", "rose"],
}


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ledger() -> dict:
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as fh:
            return json.load(fh)
    return {"version": 1, "mvs": {}}


def claimed_shas(ledger: dict, except_mv: str = "") -> dict:
    """sha256 -> mv_id for every image already stamped by another MV."""
    out = {}
    for mv, rec in ledger.get("mvs", {}).items():
        if mv == except_mv:
            continue
        for img in rec.get("images", []):
            out[img["sha256"]] = mv
    return out


def check_ledger(ledger: dict, require_files: bool = False) -> list:
    """Every violation is a failure string; an empty list means the ledger obeys
    the owner's rule: no image in two MVs, every image stamped, every MV's video
    verified. Art itself is not committed (10 MB per MV), so a missing file only
    fails when the MV's art folder is present or `require_files` is set."""
    bad = []
    owner = {}
    for mv, rec in ledger.get("mvs", {}).items():
        imgs = rec.get("images") or []
        if not imgs:
            bad.append(f"{mv}: no images stamped")
        for img in imgs:
            for key in ("path", "sha256", "prompt", "seed"):
                if key not in img:
                    bad.append(f"{mv}: image missing {key}")
            s = img.get("sha256")
            if s in owner:
                bad.append(f"image {s[:12]} reused by {owner[s]} and {mv}")
            owner[s] = mv
            p = img.get("path")
            if p:
                full = os.path.join(ROOT, p)
                if (require_files or os.path.isdir(os.path.dirname(full))) and not os.path.exists(full):
                    bad.append(f"{mv}: image file missing {p}")
        if not rec.get("video", {}).get("duration"):
            bad.append(f"{mv}: video not verified/stamped")
    return bad


def _img_gemini(prompt: str, seed: int, w: int, h: int) -> bytes | None:
    """Gemini image model ('nano banana'). Measured 2026-11-22: 429 quota, so this
    is a try-first path, not a dependency."""
    import base64
    import urllib.request
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.5-flash-image:generateContent?key={key}")
    try:
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as fh:
            d = json.load(fh)
        for cand in d.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    return base64.b64decode(part["inlineData"]["data"])
    except Exception:  # noqa: BLE001 - a dead route must fall through, not abort
        return None
    return None


def _img_procedural(mv_id: str, i: int, style: str, arc: str = "") -> tuple:
    """Generative art: no network, a new picture for every (mv, slot) seed."""
    import io

    import generative_art as ga
    names = sorted(ga.GENERATORS)
    spec = ARCS.get(arc) or {}
    names = spec.get("gens") or names
    pals = spec.get("pals") or PALETTES.get(style, PALETTES["dharma"])
    seed = int(hashlib.sha256(f"{mv_id}:proc:{i}".encode()).hexdigest()[:8], 16)
    for attempt in range(6):
        gen = names[(seed + attempt) % len(names)]
        pal = pals[(seed + attempt) % len(pals)]
        rng = __import__("numpy").random.default_rng(seed + attempt)
        img = ga.GENERATORS[gen](rng, H, W, pal, 1)
        m = ga.metrics(img)
        if m["std"] < ga.MIN_STD or m["detail"] < ga.MIN_DETAIL:
            continue
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=94)
        return buf.getvalue(), {"gen": gen, "palette": pal, "seed": seed + attempt}
    return None, {}


def generate_images(mv_id: str, style: str, n: int, out_dir: str, ledger: dict,
                    source: str = "auto", arc: str = "") -> list:
    """A fresh picture per slot, or FAIL -- never a picture another MV owns.

    Source chain (auto): gemini image -> pollinations -> procedural art. Both AI
    routes were down on 2026-11-22 (gemini 429 quota, pollinations 503), and the
    MV must still ship, so the chain falls through instead of blocking.
    """
    taken = claimed_shas(ledger)
    style_prompt = gen_cover_image.STYLES.get(style, gen_cover_image.STYLES["dharma"])
    scenes = SCENES.get(style, SCENES["dharma"])
    os.makedirs(out_dir, exist_ok=True)
    images = []
    for i in range(n):
        scene = scenes[i % len(scenes)]
        prompt = f"{scene}, {style_prompt}, music video still {i + 1} of {n}"
        got = None
        for attempt in range(4):
            seed = int(hashlib.sha256(f"{mv_id}:{i}:{attempt}".encode()).hexdigest()[:8], 16)
            data, extra, used = None, {}, ""
            if source in ("auto", "gemini"):
                data = _img_gemini(prompt, seed, W, H)
                used = "gemini"
            if data is None and source in ("auto", "pollinations"):
                data = gen_cover_image.from_pollinations(prompt, seed, W, H, tries=2)
                used = "pollinations"
            if data is None and source in ("auto", "procedural"):
                data, extra = _img_procedural(mv_id, i + attempt, style, arc)
                used = "procedural"
            if not data:
                time.sleep(2)
                continue
            digest = sha(data)
            if digest in taken:
                # Never reuse: another seed, not the same picture.
                print(f"  img{i + 1:02d}: {used} seed {seed} already used by "
                      f"{taken[digest]} -> retry")
                continue
            got = (data, digest, seed, used, extra)
            break
        if got is None:
            raise SystemExit(f"FAIL: no fresh image for {mv_id} slot {i + 1}")
        data, digest, seed, used, extra = got
        path = os.path.join(out_dir, f"img{i + 1:02d}.jpg")
        with open(path, "wb") as fh:
            fh.write(data)
        taken[digest] = mv_id
        stamp = {"path": os.path.relpath(path, ROOT), "sha256": digest,
                 "prompt": prompt, "seed": seed, "source": used}
        stamp.update(extra)
        images.append(stamp)
        print(f"  img{i + 1:02d}: {digest[:12]} {used} seed {seed}")
    return images


def build_sequence(images: list, work: str) -> str:
    parts = []
    for i, img in enumerate(images):
        frames = int(SEG_SEC * FPS)
        # Alternate push-in / pull-out so the stills do not all breathe the same way.
        z = (f"1.0+0.06*on/{frames}" if i % 2 == 0 else f"1.06-0.06*on/{frames}")
        zoom = (f"scale={int(W * 1.1)}:{int(H * 1.1)},"
                f"zoompan=z='{z}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={W}x{H}:fps={FPS},format=yuv420p")
        seg = os.path.join(work, f"seg{i:02d}.mp4")
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
             "-i", os.path.join(ROOT, img["path"]), "-vf", zoom,
             "-t", f"{SEG_SEC:.3f}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-color_range", "tv", "-colorspace", "bt709",
             "-color_primaries", "bt709", "-color_trc", "bt709",
             "-pix_fmt", "yuv420p", seg])
        parts.append(seg)
    listing = os.path.join(work, "seq.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    seq = os.path.join(work, "seq.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing, "-c", "copy", seq])
    return seq


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,pix_fmt,color_range,r_frame_rate",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    return {"duration": float(d["format"]["duration"]),
            "width": v.get("width"), "height": v.get("height"),
            "pix_fmt": v.get("pix_fmt"), "color_range": v.get("color_range"),
            "fps": v.get("r_frame_rate")}


def loudness(path: str) -> tuple:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    tail = out.split("Summary:")[-1]
    i = re.search(r"I:\s*(-?\d+\.\d+)\s*LUFS", tail)
    p = re.search(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", tail)
    return (float(i.group(1)) if i else float("nan"),
            float(p.group(1)) if p else float("nan"))


def assemble(seq: str, music: str, seconds: float, out: str) -> None:
    fade_out = max(0.0, seconds - 8.0)
    # TP=-3.5 leaves room for the AAC overshoot: measured 2026-11-22, TP=-1.5
    # in loudnorm shipped a -2.2 dBFS file and failed the -3.0 gate.
    base = (f"loudnorm=I=-14:TP=-3.5:LRA=11,"
            f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out:.3f}:d=8")

    def encode(gain_db: float = 0.0) -> None:
        af = f"volume={gain_db:.2f}dB,{base}" if gain_db else base
        run(["ffmpeg", "-y", "-loglevel", "error",
             "-stream_loop", "-1", "-i", seq, "-stream_loop", "-1", "-i", music,
             "-map", "0:v", "-map", "1:a", "-t", f"{seconds:.3f}",
             "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", out])

    ceiling = TP_CEILING - TP_MARGIN
    gain = 0.0
    for _ in range(3):
        encode(gain)
        _, peak = loudness(out)
        if not (peak > ceiling):
            return
        gain += ceiling - peak


def verify(path: str, minutes: float) -> dict:
    info = probe(path)
    lufs, tp = loudness(path)
    fails = []
    if abs(info["duration"] - minutes * 60) > 2.0:
        fails.append(f"duration {info['duration']:.1f}s != {minutes * 60:.0f}s")
    if (info["width"], info["height"]) != (W, H):
        fails.append(f"picture {info['width']}x{info['height']}")
    if info["pix_fmt"] != "yuv420p":
        fails.append(f"pix_fmt {info['pix_fmt']}")
    if info["color_range"] != "tv":
        fails.append(f"color_range {info['color_range']}")
    if not (LUFS_MIN <= lufs <= LUFS_MAX):
        fails.append(f"loudness {lufs} outside {LUFS_MIN}..{LUFS_MAX}")
    if tp > TP_CEILING:
        fails.append(f"true peak {tp} > {TP_CEILING}")
    return {"verdict": "pass" if not fails else "fail", "failures": fails,
            "duration": info["duration"], "lufs": lufs, "true_peak": tp,
            "picture": f"{info['width']}x{info['height']}", "color_range": info["color_range"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mv-id", required=True)
    ap.add_argument("--style", default="dharma", choices=sorted(SCENES))
    ap.add_argument("--title", required=True)
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--images", type=int, default=12)
    ap.add_argument("--music", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=None)
    ap.add_argument("--arc", default="auto",
                    help="visual story for this MV; 'auto' picks the first arc the "
                         "channel has not used")
    ap.add_argument("--channel", default="dharma")
    ap.add_argument("--resume", action="store_true",
                    help="reuse the images a failed run already stamped")
    ap.add_argument("--source", default="auto",
                    choices=["auto", "gemini", "pollinations", "procedural"])
    a = ap.parse_args()

    import content_ledger as cl
    used = [rec.get("arc") for rec in cl.load()["videos"].values()
            if rec.get("channel") == a.channel and rec.get("arc")]
    if a.arc == "auto":
        a.arc = next((x for x in ARCS if x not in used), "")
        if not a.arc:
            sys.exit("FAIL: every arc is used on this channel; add one to ARCS")
    elif a.arc in used:
        sys.exit(f"FAIL: arc {a.arc} already aired on {a.channel}")
    music_sha = cl.file_sha(os.path.join(ROOT, a.music) if not os.path.isabs(a.music) else a.music)
    for key, rec in cl.load()["videos"].items():
        if rec.get("channel") == a.channel and (rec.get("music") or {}).get("sha256") == music_sha:
            sys.exit(f"FAIL: music bed already used by {key} on {a.channel}")
    print(f"== arc: {a.arc}")

    ledger = load_ledger()
    existing = ledger["mvs"].get(a.mv_id)
    if existing and not a.resume:
        sys.exit(f"FAIL: {a.mv_id} already has a stamped MV")
    if existing and existing.get("video", {}).get("duration"):
        sys.exit(f"FAIL: {a.mv_id} already has a verified video")
    work = a.work or os.path.join(ROOT, "work", "mv", a.mv_id)
    os.makedirs(work, exist_ok=True)

    if existing:
        images = existing["images"]
        missing = [i["path"] for i in images
                   if not os.path.exists(os.path.join(ROOT, i["path"]))]
        if missing:
            sys.exit(f"FAIL: resume but images are gone: {missing[:3]}")
        print(f"== images: resuming the {len(images)} already stamped")
    else:
        print(f"== images: {a.images} fresh, style {a.style}")
        images = generate_images(a.mv_id, a.style, a.images,
                                 os.path.join(ROOT, "assets", "art", "mv", a.mv_id),
                                 ledger, source=a.source, arc=a.arc)
    # Stamp the claim before the long render: a crash must not free the images.
    ledger["mvs"][a.mv_id] = {"title": a.title, "style": a.style, "created":
                              time.strftime("%Y-%m-%dT%H:%M:%S%z"), "images": images,
                              "music": {"path": os.path.relpath(a.music, ROOT),
                                        "sha256": file_sha(a.music)},
                              "video": {}, "published": {}}
    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2)

    print("== sequence")
    seq = build_sequence(images, work)
    print("== assemble")
    assemble(seq, a.music, a.minutes * 60, a.out)
    v = verify(a.out, a.minutes)
    print(json.dumps(v, ensure_ascii=False))
    if v["verdict"] != "pass":
        sys.exit(f"FAIL: {v['failures']}")

    cl.stamp(a.mv_id, a.channel, [], title=a.title, music=a.music, arc=a.arc,
             kind="music")
    ledger["mvs"][a.mv_id]["video"] = {
        "path": os.path.relpath(a.out, ROOT), "sha256": file_sha(a.out),
        "duration": v["duration"], "lufs": v["lufs"], "true_peak": v["true_peak"]}
    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2)
    bad = check_ledger(ledger)
    if bad:
        sys.exit(f"FAIL: ledger {bad}")
    print(f"stamped: {a.mv_id} -> {len(images)} images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
