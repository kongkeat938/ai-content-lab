#!/usr/bin/env python3
"""Package a finished order: clips + thumbnails + a SHA-256 manifest, in one ZIP.

The client gets a file whose integrity they can check themselves, and we get a
record of exactly what was sent (a dispute later has an answer).

    python3 scripts/deliver.py --order o1 --src /tmp/order_v4 --out deliveries

Refuses (exit 1) if a file cannot be probed or the ZIP does not read back with
the same hashes it recorded. Exits 2 with no ffprobe -- blind is not "fine".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,codec_name,width,height,pix_fmt,color_range:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr.strip()[:200]}")
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"width": v.get("width"), "height": v.get("height"), "codec": v.get("codec_name"),
            "pix_fmt": v.get("pix_fmt"), "color_range": v.get("color_range"),
            "duration_s": round(float(d.get("format", {}).get("duration", 0)), 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "deliveries"))
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if subprocess.run(["which", "ffprobe"], capture_output=True).returncode != 0:
        print("BLIND: ffprobe not found -- cannot certify what is being delivered", file=sys.stderr)
        return 2
    if not os.path.isdir(a.src):
        print(f"BLIND: no such directory {a.src}", file=sys.stderr)
        return 2

    clips = sorted(f for f in os.listdir(a.src) if f.lower().endswith(".mp4"))
    if not clips:
        print(f"BLIND: no .mp4 in {a.src}", file=sys.stderr)
        return 2

    files = []
    for name in clips:
        path = os.path.join(a.src, name)
        try:
            info = probe(path)
        except RuntimeError as e:
            print(f"FAIL: {e}")
            return 1
        entry = {"name": name, "bytes": os.path.getsize(path), "sha256": sha256(path), **info}
        thumb = os.path.splitext(path)[0] + ".jpg"
        if os.path.exists(thumb):
            entry["thumbnail"] = {"name": os.path.basename(thumb), "bytes": os.path.getsize(thumb),
                                  "sha256": sha256(thumb)}
        files.append(entry)

    os.makedirs(a.out, exist_ok=True)
    manifest = {"order": a.order, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "note": a.note, "files": files}
    mpath = os.path.join(a.out, f"{a.order}.manifest.json")
    json.dump(manifest, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    zpath = os.path.join(a.out, f"{a.order}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for entry in files:
            z.write(os.path.join(a.src, entry["name"]), f"clips/{entry['name']}")
            if "thumbnail" in entry:
                z.write(os.path.join(a.src, entry["thumbnail"]["name"]),
                        f"thumbs/{entry['thumbnail']['name']}")
        z.write(mpath, "manifest.json")

    # read the ZIP back: a package nobody verified is a claim, not a delivery
    with zipfile.ZipFile(zpath) as z:
        for entry in files:
            got = hashlib.sha256(z.read(f"clips/{entry['name']}")).hexdigest()
            if got != entry["sha256"]:
                print(f"FAIL: {entry['name']} changed inside the zip")
                return 1
        if "manifest.json" not in z.namelist():
            print("FAIL: manifest.json missing from the zip")
            return 1

    total = sum(f["bytes"] for f in files)
    print(f"ok   {a.order}: {len(files)} clip(s), {total/1e6:.1f} MB -> {zpath}")
    print(f"     manifest {mpath}")
    for f in files:
        print(f"     {f['name']:24} {f['width']}x{f['height']} {f['duration_s']:.2f}s {f['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
