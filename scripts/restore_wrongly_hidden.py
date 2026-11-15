#!/usr/bin/env python3
"""Restore the clips that a FALSE "rogue" label hid.

Measured 2026-11-15: the audit called any unrecorded upload a "live rogue upload
outside the rails" and paused it (privacyStatus=private). The real source was the
predecessor rail `kongkeat938/ax-workspace .github/workflows/auto-shorts.yml` --
OUR OWN -- which published to the same three channels with the same secrets and
recorded them only in its own `docs/published.json`. 30 of the 32 clips in
`content/rogue_hidden.json` are in fact ours, so they were hidden on a false label
(25 were later deleted by the private-delete rail; 5 remain, hidden).

This puts back the ones that are still merely hidden -- never a deleted one (the API
cannot un-delete; those are reported, not touched). It is idempotent, dry-run by
default, and a no-op when the daily quota is spent (it then says so and exits 0, so
the rail can retry after the 08:00 UTC reset).

    python3 scripts/restore_wrongly_hidden.py            # list what would be restored
    python3 scripts/restore_wrongly_hidden.py --apply    # set them back to public
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import yt_auth  # noqa: E402

HIDDEN = os.path.join(ROOT, "content", "rogue_hidden.json")
KNOWN = os.path.join(ROOT, "content", "known_uploads.json")
CHANNEL_TOKEN = {
    "UCI6EfsgM1HNjrYarvigxyrQ": "YT_CH1_REFRESH_TOKEN",
    "UCM3QO5L_pmj34n1JVlbhh-w": "YT_CH2_REFRESH_TOKEN",
    "UC7gCIu4G_7QCEJ8hJ-34zoQ": "YT_CH4_REFRESH_TOKEN",
}


def wrongly_hidden() -> list[dict]:
    """Hidden clips that a sibling rail actually recorded -- ours, wrongly paused."""
    hidden = json.load(open(HIDDEN, encoding="utf-8")).get("hidden", [])
    known = {u["video_id"] for u in
             json.load(open(KNOWN, encoding="utf-8")).get("uploads", [])}
    return [h for h in hidden if h.get("video_id") in known]


def restore(apply: bool) -> int:
    targets = wrongly_hidden()
    if not targets:
        print("nothing to restore: no hidden clip is a recorded sibling-rail upload")
        return 0
    by_channel: dict[str, list] = {}
    for h in targets:
        by_channel.setdefault(h["channel_id"], []).append(h)

    from googleapiclient.discovery import build

    restored, gone, blocked = [], [], 0
    for cid, items in by_channel.items():
        var = CHANNEL_TOKEN.get(cid)
        if not var or not os.environ.get(var):
            print(f"{cid}: no {var} in the environment; skipping {len(items)}")
            blocked += len(items)
            continue
        creds = yt_auth.load_credentials(cid)
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        ids = [h["video_id"] for h in items]
        status = {}
        try:
            for i in range(0, len(ids), 50):
                r = yt.videos().list(part="status", id=",".join(ids[i:i + 50])).execute()
                for it in r.get("items", []):
                    status[it["id"]] = it.get("status", {}).get("privacyStatus")
        except Exception as exc:  # quota 403 is expected before the 08:00 UTC reset
            print(f"{cid}: read failed ({str(exc)[:100]}); quota likely spent, "
                  f"retry after the 08:00 UTC reset")
            blocked += len(items)
            continue
        for h in items:
            vid = h["video_id"]
            cur = status.get(vid)
            if cur is None:
                gone.append((vid, h.get("title", "")))
                continue
            if cur == "public":
                print(f"  {vid} already public")
                continue
            if not apply:
                print(f"  would restore {vid} ({cur} -> public): {h.get('title','')[:50]}")
                continue
            try:
                yt.videos().update(part="status", body={
                    "id": vid, "status": {"privacyStatus": "public"}}).execute()
                restored.append((vid, h.get("title", "")))
                print(f"  restored {vid} -> public: {h.get('title','')[:50]}")
            except Exception as exc:  # quota 403 is expected before the reset
                print(f"  could not restore {vid}: {str(exc)[:120]}")
                blocked += 1

    if apply:
        # Drop every id this run resolved -- restored ones AND the known-but-gone
        # (deleted) ones. Leaving the deleted ones in the ledger would keep the
        # foreman's "a wrongly-hidden clip remains" condition true forever and it
        # would dispatch this rail every day for nothing.
        resolved = {v for v, _ in restored} | {v for v, _ in gone}
        if resolved:
            doc = json.load(open(HIDDEN, encoding="utf-8"))
            doc["hidden"] = [h for h in doc.get("hidden", []) if h.get("video_id") not in resolved]
            json.dump(doc, open(HIDDEN, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"removed {len(resolved)} resolved id(s) from "
                  f"{os.path.relpath(HIDDEN, ROOT)} (restored or confirmed gone)")

    print(f"\nsummary: restored={len(restored)} already_gone={len(gone)} blocked={blocked} "
          f"of {len(targets)}")
    if gone:
        print("permanently gone (deleted; cannot be restored by the API):")
        for vid, t in gone:
            print(f"  {vid} {t[:50]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually set the clips back to public (default: dry run)")
    args = ap.parse_args()
    return restore(args.apply)


if __name__ == "__main__":
    sys.exit(main())
