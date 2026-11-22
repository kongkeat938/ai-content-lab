"""Stamp what each published clip is made of, so a follower never hears it twice.

The owner's rule (K, 2026-11-22): "เนื้อเรื่องแต่ละคลิป ก็อย่าซ้ำกัน" -- the story
of each clip must be new, not just the pictures. Nothing recorded that before, so
two compilations could share the same parts and no guard could tell. This ledger
is the record: per video key, the parts it used (by normalised text sha256), its
music bed, its visual arc and its title.

`check()` is the guard: one part in two videos, one title twice on a channel, or
one music bed twice on a channel is a failure, and it must be able to fail.

Usage:
    python3 content_ledger.py check
    python3 content_ledger.py stamp --key night_90_x --channel dharma \
        --parts content/night_auto_202645 --title "..." --music assets/music/bed.mp3
    python3 content_ledger.py report
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(ROOT, "content", "content_ledger.json")


def norm(text: str) -> str:
    return " ".join(text.split())


def text_sha(text: str) -> str:
    return hashlib.sha256(norm(text).encode("utf-8")).hexdigest()


def file_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load() -> dict:
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as fh:
            return json.load(fh)
    return {"version": 1, "videos": {}}


def save(ledger: dict) -> None:
    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2)


def parts_of(content_dir: str) -> list:
    """Every narration piece in a content directory, stamped by text sha."""
    out = []
    if not os.path.isdir(content_dir):
        return out
    for f in sorted(os.listdir(content_dir)):
        if not f.endswith((".txt", ".md")):
            continue
        text = open(os.path.join(content_dir, f), encoding="utf-8", errors="ignore").read()
        if len(norm(text)) < 80:      # a title card, not a story
            continue
        out.append({"id": f, "sha256": text_sha(text), "words": len(norm(text).split())})
    return out


def used_parts(ledger: dict, except_key: str = "") -> dict:
    """sha256 -> video key, for every part another video already used."""
    out = {}
    for key, rec in ledger.get("videos", {}).items():
        if key == except_key:
            continue
        for p in rec.get("parts", []):
            out[p["sha256"]] = key
    return out


def check(ledger: dict) -> list:
    bad = []
    owner = {}
    titles = {}
    music = {}
    for key, rec in ledger.get("videos", {}).items():
        parts = rec.get("parts") or []
        if not parts and not rec.get("arc"):
            bad.append(f"{key}: nothing stamped (no parts, no arc)")
        for p in parts:
            for f in ("id", "sha256"):
                if f not in p:
                    bad.append(f"{key}: part missing {f}")
            s = p.get("sha256")
            if s in owner:
                bad.append(f"part {p.get('id')} of {key} already used by {owner[s]}")
            owner[s] = key
        ch = rec.get("channel", "?")
        t = norm(rec.get("title", "")).lower()
        if t:
            if (ch, t) in titles:
                bad.append(f"title repeated on {ch}: {titles[(ch, t)]} and {key}")
            titles[(ch, t)] = key
        m = (rec.get("music") or {}).get("sha256")
        if m:
            if (ch, m) in music:
                bad.append(f"music bed repeated on {ch}: {music[(ch, m)]} and {key}")
            music[(ch, m)] = key
    return bad


def stamp(key: str, channel: str, parts=None, title: str = "", music: str = "",
          arc: str = "", url: str = "", kind: str = "") -> dict:
    ledger = load()
    rec = ledger["videos"].get(key, {})
    if parts is not None:
        rec["parts"] = parts
    rec.update({"channel": channel, "kind": kind or ("narration" if parts else "music"),
                "stamped": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    if title:
        rec["title"] = title
    if arc:
        rec["arc"] = arc
    if url:
        rec["url"] = url
    if music:
        rec["music"] = {"path": os.path.relpath(music, ROOT) if os.path.isabs(music) else music,
                        "sha256": file_sha(music) if os.path.exists(music)
                        else file_sha(os.path.join(ROOT, music))}
    ledger["videos"][key] = rec
    save(ledger)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["check", "stamp", "report"])
    ap.add_argument("--key")
    ap.add_argument("--channel", default="dharma")
    ap.add_argument("--parts", help="content directory of numbered .txt pieces")
    ap.add_argument("--title", default="")
    ap.add_argument("--music", default="")
    ap.add_argument("--arc", default="")
    ap.add_argument("--url", default="")
    a = ap.parse_args()

    if a.action == "check":
        bad = check(load())
        for b in bad:
            print("FAIL", b)
        print("OK" if not bad else f"{len(bad)} violations")
        return 0 if not bad else 1

    if a.action == "report":
        led = load()
        by_ch = {}
        for key, rec in led["videos"].items():
            ch = rec.get("channel", "?")
            d = by_ch.setdefault(ch, {"videos": 0, "parts": set(), "titles": set()})
            d["videos"] += 1
            d["parts"].update(p["sha256"] for p in rec.get("parts", []))
            d["titles"].add(rec.get("title", ""))
        for ch, d in sorted(by_ch.items()):
            print(f"{ch}: {d['videos']} videos, {len(d['parts'])} distinct parts, "
                  f"{len(d['titles'])} titles")
        return 0

    if not a.key:
        ap.error("stamp needs --key")
    parts = parts_of(a.parts) if a.parts else None
    if parts:
        clash = {p["id"]: used_parts(load(), a.key).get(p["sha256"]) for p in parts}
        clash = {k: v for k, v in clash.items() if v}
        if clash:
            print(f"FAIL: parts already used by another video: {clash}")
            return 1
    rec = stamp(a.key, a.channel, parts, a.title, a.music, a.arc, a.url)
    print(f"stamped {a.key}: {len(rec.get('parts', []))} parts, arc={rec.get('arc', '-')}")
    bad = check(load())
    if bad:
        print("FAIL after stamp:", bad)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
