#!/usr/bin/env python3
"""Restore the description + tags that `videos.update` erased.

Measured 2026-11-14: `optimize_titles.apply_title` and `apply_packaging.set_title_tags`
wrote `part=snippet` bodies without `description`, and `videos.update` REPLACES the whole
snippet -- so every retitle/packaging pass wiped the description and tags. On genx alone,
123/146 clips had no tags and 120 of them were retitled. The description carries the
subscribe ask and the tail link, so this is a subscriber lever that was erased.

The original metadata is recoverable from the manifests:
  * Shorts: `content/<ch>_shorts/scripts.json` (hook/lines/cta) + the channel spec's tail,
    exactly the string `publish_shorts` uploaded.
  * Long-form: `content/<ch>_publish.json` stores the exact `description` + `tags`.

Only clips MISSING a description or tags are touched, so this is idempotent. A
`videos.update` costs 50 quota units and the daily cap is 10,000, so a full restore cannot
finish in one run -- it stops cleanly on `quotaExceeded` and `docs/metadata_restore.json`
skips whatever is done, so the next run (after the 08:00 UTC reset) continues.

    python3 scripts/restore_metadata.py --channel genx          # plan only
    python3 scripts/restore_metadata.py --channel all --apply   # write
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402
from analytics import access_token  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/videos"
LEDGER = os.path.join(ROOT, "docs", "metadata_restore.json")
LONGFORM = {"genx": "ch1_publish.json", "dharma": "ch2_publish.json",
            "kongkeat": "ch4_publish.json"}


def short_targets(ch: str) -> dict[str, dict]:
    spec = ps.CHANNELS[ch]
    scripts = {x["id"]: x for x in json.load(open(spec["scripts"], encoding="utf-8"))}
    man = json.load(open(spec["manifest"], encoding="utf-8"))["shorts"]
    out = {}
    for key, e in man.items():
        vid, s = e.get("video_id"), scripts.get(key)
        if not vid or not s:
            continue
        desc = (f"{s['hook']}\n\n" + "\n".join(s["lines"]) + f"\n\n{s['cta']}"
                + spec["tail"] + (ps.MUSIC_CREDIT if spec.get("music_dir") else ""))
        out[vid] = {"description": desc[:5000], "tags": spec["tags"],
                    "category": spec.get("category", "22")}
    return out


def longform_targets(ch: str) -> dict[str, dict]:
    path = os.path.join(ROOT, "content", LONGFORM[ch])
    if not os.path.exists(path):
        return {}
    d = json.load(open(path, encoding="utf-8"))
    out = {}
    for v in d.get("videos", []):
        vid = v.get("video_id")
        if not vid or not (v.get("description") or v.get("tags")):
            continue
        out[vid] = {"description": (v.get("description") or "")[:5000],
                    "tags": v.get("tags") or [],
                    "category": v.get("category_id", "22")}
    return out


def current(vids: list[str], token: str) -> dict[str, dict]:
    out = {}
    for i in range(0, len(vids), 50):
        ids = ",".join(vids[i:i + 50])
        req = urllib.request.Request(
            f"{API}?part=snippet&id={ids}&maxResults=50",
            headers={"Authorization": f"Bearer {token}"})
        for it in json.load(urllib.request.urlopen(req, timeout=30)).get("items", []):
            out[it["id"]] = it["snippet"]
    return out


def needs_restore(sn: dict) -> bool:
    """True when a snippet lost its description or its tags."""
    return not (sn.get("description") or "").strip() or not sn.get("tags")


def put(vid: str, sn: dict, target: dict, token: str) -> None:
    body = {"id": vid, "snippet": {
        "title": sn.get("title", ""),
        "description": target["description"],
        "tags": target["tags"],
        "categoryId": sn.get("categoryId", target["category"]),
    }}
    for k in ("defaultLanguage", "defaultAudioLanguage"):
        if sn.get(k) is not None:
            body["snippet"][k] = sn[k]
    req = urllib.request.Request(f"{API}?part=snippet", data=json.dumps(body).encode(),
                                 method="PUT",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=40)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="genx",
                    choices=["genx", "dharma", "kongkeat", "all"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="max writes this run (0 = no cap)")
    a = ap.parse_args()

    chans = list(ps.CHANNELS) if a.channel == "all" else [a.channel]
    done = set()
    if os.path.exists(LEDGER):
        done = {c["video_id"] for c in json.load(open(LEDGER, encoding="utf-8")).get("changes", [])}

    changes, wrote = [], 0
    quota_hit = False
    for ch in chans:
        if quota_hit:
            break
        targets = short_targets(ch) | longform_targets(ch)
        token = access_token(ps.CHANNELS[ch]["token"])
        try:
            cur = current(list(targets), token)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="ignore")
            if exc.code == 403 and "quotaExceeded" in body:
                print(f"== {ch}: read quota exhausted -- re-run after 08:00 UTC reset")
                quota_hit = True
                continue
            raise
        need = []
        for vid, tgt in targets.items():
            if vid in done:
                continue
            sn = cur.get(vid)
            if not sn:
                continue
            if not needs_restore(sn):
                continue
            need.append((vid, sn, tgt))
        print(f"== {ch}: {len(targets)} known, {len(need)} need a restore")
        if not a.apply:
            for vid, sn, _ in need[:5]:
                print(f"   {vid} desc={len((sn.get('description') or ''))} "
                      f"tags={len(sn.get('tags') or [])}")
            continue
        for vid, sn, tgt in need:
            if a.limit and wrote >= a.limit:
                print(f"   reached --limit {a.limit}")
                break
            try:
                put(vid, sn, tgt, token)
                changes.append({"video_id": vid, "channel": ch,
                                "at": datetime.now(timezone.utc).isoformat()})
                wrote += 1
                print(f"   restored {vid}")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(errors="ignore")
                if exc.code == 403 and "quotaExceeded" in body:
                    print("   DAILY QUOTA REACHED -- stopping; re-run after 08:00 UTC reset")
                    quota_hit = True
                    break
                print(f"   {vid}: FAILED {exc.code} {body[:120]}")
    if a.apply:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        prev = json.load(open(LEDGER, encoding="utf-8")).get("changes", []) if os.path.exists(LEDGER) else []
        json.dump({"changes": prev + changes}, open(LEDGER, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"\nrestored {len(changes)} clip(s); ledger {os.path.relpath(LEDGER, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
