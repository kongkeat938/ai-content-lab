#!/usr/bin/env python3
"""The ONE image vault every channel draws from -- and the stamp that bans reuse.

Owner K (2026-11-20): "หลักสำคัญ แต่ละคลิปห้ามใช้รูปเดียวกัน ทุกช่องด้วย รูปไหนเอามาใช้
แล้วต้อง stamp ไว้เลยว่าห้ามใช้ รูปต้องสร้างเก็บไว้เรื่อยๆ จะมีสะสมในโกดังเอง" -- one image
per clip, never repeated, **across every channel**, stamped the moment it is used, and
stock accumulated in a warehouse.

Why this file exists rather than a new ledger: the per-channel ledgers
(`content/art_ledger_<channel>.json`) were keyed by md5 *within one channel*, so two
channels could hand out the same picture and no check would notice. Measured
2026-11-20 on the committed ledgers: **4 md5 were already shared between `motion`
and `motion2`**, i.e. the defect was real, not hypothetical. This module keeps ONE
index for all channels and merges the old ledgers into it so no history is lost.

The stamp is the ledger entry itself. An image is "free" only when its md5 is absent
from the vault; the moment a clip takes it, the md5 is written with the channel, the
clip id and the time, and every later claim -- any channel -- is refused.

    python3 scripts/image_vault.py status
    python3 scripts/image_vault.py merge          # fold old per-channel ledgers in
    python3 scripts/image_vault.py claim --file a.png --channel dharma --clip ep07
    python3 scripts/image_vault.py stamp --md5 <hash> --channel genx --clip 42

The read-pick-write is done under an exclusive lock on the vault file. Measured
2026-11-19 on the older per-channel path: without a lock two builders read the same
ledger, picked the same free picture and both wrote themselves down -- the exact
"two clips share one image" the owner forbade. The lock is what makes this a claim
and not a note.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.join(ROOT, "content", "image_vault.json")
CHANNELS = ("dharma", "genx", "kongkeat", "motion", "motion2")

_DOC = ("One image, one clip, every channel (K, 2026-11-20). An md5 present here is "
        "BANNED for reuse: `stamp` writes it the moment a clip takes the picture. "
        "Merged from the old per-channel art_ledger_*.json, which could not see "
        "across channels (4 md5 were already shared). Never delete an entry -- "
        "deleting one un-bans an image that is already live in a video.")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _empty() -> dict:
    return {"_doc": _DOC, "images": {}}


def load(path: str = VAULT) -> dict:
    if not os.path.exists(path):
        return _empty()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"vault is unreadable: {exc}") from exc
    data.setdefault("images", {})
    return data


def save(data: dict, path: str = VAULT) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def lock(path: str = VAULT):
    """Exclusive lock for a read-pick-write, reusing the house implementation."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import make_short as MS

    return MS.ledger_lock(path)


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_used(md5: str, data: dict) -> bool:
    """True only when a clip has SPENT this picture.

    Presence in the vault is not enough: a stocked picture (`clip` empty) is
    free stock waiting to be taken, and counting it as used is what made the
    warehouse hand nothing out (measured 2026-11-20).
    """
    rec = data.get("images", {}).get(md5)
    return bool(rec and rec.get("clip"))


def free_stock(data: dict) -> list:
    """md5 of every stocked picture no clip has taken yet."""
    return [m for m, r in data.get("images", {}).items() if not r.get("clip")]


def stamp(md5: str, channel: str, clip: str, file: str = "",
          path: str = VAULT) -> dict:
    """Ban this image for every channel. Idempotent only for the SAME clip.

    A picture still in stock (`clip` empty) is the intended take: the warehouse
    exists so a clip can draw from it. Re-stamping an md5 a DIFFERENT clip
    already holds is refused -- that is the reuse the owner forbade, and it must
    fail loudly rather than overwrite the record of who used it first.
    """
    with lock(path):
        data = load(path)
        have = data["images"].get(md5)
        holder = (have or {}).get("clip")
        if holder and holder != str(clip):
            raise RuntimeError(
                f"image already used by {have.get('channel')}/{holder} "
                f"(this claim: {channel}/{clip}) -- reuse is banned on every channel")
        data["images"][md5] = {"channel": channel, "clip": str(clip),
                               "file": os.path.basename(file) if file else
                               (have or {}).get("file", ""),
                               "stamped_at": (have or {}).get("stamped_at") or now()}
        save(data, path)
        return data["images"][md5]


def claim_file(path_in: str, channel: str, clip: str, vault: str = VAULT) -> str:
    """Stamp a picture and return its md5, or raise if it is already taken."""
    md5 = md5_of(path_in)
    stamp(md5, channel, clip, path_in, vault)
    return md5


def pick_free(candidates: list, channel: str, clip: str, vault: str = VAULT) -> str:
    """Take the first candidate no clip has spent, stamp it, and return it.

    A candidate still in stock is exactly what the warehouse is for, so it is
    taken rather than skipped. Read-pick-write happens under one lock, so two
    clips racing cannot both take the same file.
    """
    with lock(vault):
        data = load(vault)
        for cand in candidates:
            md5 = md5_of(cand)
            have = data["images"].get(md5) or {}
            holder = have.get("clip")
            if holder and holder != str(clip):
                continue
            rec = dict(have)
            rec.update({"channel": channel, "clip": str(clip),
                        "file": os.path.basename(cand),
                        "stamped_at": have.get("stamped_at") or now()})
            data["images"][md5] = rec
            save(data, vault)
            return cand
    raise RuntimeError(f"no unused image left for {channel}/{clip} "
                       f"({len(candidates)} candidates, all stamped)")


def merge_legacy(vault: str = VAULT) -> dict:
    """Fold the old per-channel ledgers in, without losing who used what."""
    added = 0
    with lock(vault):
        data = load(vault)
        for path in sorted(glob.glob(os.path.join(ROOT, "content",
                                                  "art_ledger_*.json"))):
            channel = os.path.basename(path)[len("art_ledger_"):-len(".json")]
            try:
                with open(path, encoding="utf-8") as fh:
                    md5map = json.load(fh).get("md5", {})
            except (OSError, ValueError):
                continue
            for md5, clip in md5map.items():
                have = data["images"].get(md5)
                if have:
                    # Keep the first owner; record the second channel as evidence.
                    others = set(have.get("also_seen_in", []))
                    if have.get("channel") != channel:
                        others.add(channel)
                        have["also_seen_in"] = sorted(others)
                    continue
                data["images"][md5] = {"channel": channel, "clip": str(clip),
                                       "file": "", "stamped_at": now(),
                                       "merged_from": f"art_ledger_{channel}.json"}
                added += 1
        save(data, vault)
    return {"added": added, "total": len(load(vault)["images"])}


def cross_channel_dupes(data: dict | None = None) -> dict:
    """md5 claimed by more than one channel -- must be empty once merged."""
    data = data or load()
    out = {}
    for md5, rec in data.get("images", {}).items():
        seen = set(rec.get("also_seen_in", [])) | {rec.get("channel")}
        if len(seen) > 1:
            out[md5] = sorted(seen)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["status", "merge", "claim", "stamp"])
    ap.add_argument("--file")
    ap.add_argument("--md5")
    ap.add_argument("--channel", default="")
    ap.add_argument("--clip", default="")
    ap.add_argument("--vault", default=VAULT)
    args = ap.parse_args()

    if args.action == "status":
        data = load(args.vault)
        by_ch = {}
        for rec in data["images"].values():
            by_ch[rec.get("channel", "?")] = by_ch.get(rec.get("channel", "?"), 0) + 1
        print(json.dumps({"total_banned": len(data["images"]),
                          "by_channel": dict(sorted(by_ch.items())),
                          "cross_channel_reuse": cross_channel_dupes(data)},
                         indent=1, ensure_ascii=False))
        return 0
    if args.action == "merge":
        print(json.dumps(merge_legacy(args.vault), indent=1))
        return 0
    if not (args.channel and args.clip):
        raise SystemExit("--channel and --clip are required for claim/stamp")
    if args.action == "claim":
        if not args.file:
            raise SystemExit("--file is required for claim")
        print(claim_file(args.file, args.channel, args.clip, args.vault))
        return 0
    if not args.md5:
        raise SystemExit("--md5 is required for stamp")
    print(json.dumps(stamp(args.md5, args.channel, args.clip, "", args.vault),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
