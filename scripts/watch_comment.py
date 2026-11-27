#!/usr/bin/env python3
"""Watch a posted comment for 24 hours: present, unchanged, not held.

A comment can disappear after it looks fine -- a spam filter, a moderation pass
or the owner removing it. The CTA test only means something if the comment is
still there at 1h, 6h and 24h, so each check is recorded rather than remembered.

    python3 scripts/watch_comment.py --label 1h
    python3 scripts/watch_comment.py --label 6h --json

Exit codes: 0 = present and text unchanged, 2 = absent or edited (BLIND), and
the record says which, so "cannot read" never passes as "still fine".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

CHANNEL_ID = {"dharma": "UCM3QO5L_pmj34n1JVlbhh-w",
              "genx": "UCI6EfsgM1HNjrYarvigxyrQ",
              "kongkeat-story": "UC7gCIu4G_7QCEJ8hJ-34zoQ"}
DEFAULT = {"dharma": {"comment_id": "UgzRD13qTn8lhuI0IA54AaABAg",
                      "expect": "PLBpZCGnd7Q5Y"}}
LEDGER = "content/comment_watch_{slug}.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", default="dharma", choices=list(CHANNEL_ID))
    ap.add_argument("--comment-id")
    ap.add_argument("--expect", help="substring the comment text must still carry")
    ap.add_argument("--label", default="check", help="1h / 6h / 24h")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    seed = DEFAULT.get(args.slug, {})
    cid = args.comment_id or seed.get("comment_id")
    expect = args.expect or seed.get("expect", "")
    if not cid:
        print("refusing: no comment id and no default for this channel", file=sys.stderr)
        return 2

    import yt_auth
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    creds = yt_auth.load_credentials(CHANNEL_ID[args.slug])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    state, text, detail = "absent", "", ""
    try:
        r = yt.comments().list(part="snippet", id=cid, textFormat="plainText").execute()
        items = r.get("items", [])
    except HttpError as exc:
        state, detail = "blind", f"HTTP {exc.resp.status}"
        items = []
    if items:
        text = items[0]["snippet"].get("textDisplay", "")
        if expect and expect not in text:
            state, detail = "edited", f"missing {expect!r}"
        else:
            state = "present"

    rec = {"checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "label": args.label, "comment_id": cid, "state": state, "detail": detail,
           "text_head": text[:120]}
    path = os.path.join(ROOT, LEDGER.format(slug=args.slug))
    log = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                log = json.load(fh)
        except ValueError:
            log = []
    log.append(rec)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)

    if args.json:
        print(json.dumps(rec, ensure_ascii=False))
    else:
        print(f"{args.label}: {state} {detail} ({cid})")
    return 0 if state == "present" else 2


if __name__ == "__main__":
    sys.exit(main())
