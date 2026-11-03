#!/usr/bin/env python3
"""Ask Gemini for advice, with the real numbers attached.

K's standing order is that I take decisions myself and consult an AI rather than
ask a person. This is that consultant: it sends a question plus the channel's
measured state, so the advice is about the actual channel and not a generic
YouTube tutorial.

    python3 scripts/consult.py "what should I change first?"
    python3 scripts/consult.py --model gemini-3.5-flash-lite "..."

Needs GEMINI_API_KEY. gemini-3.5-flash-lite is the only model that answers on the
free key (measured 2026-11-03).
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
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def load(rel: str, default):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def channel_state() -> dict:
    """The facts the consultant should reason from, gathered from the ledgers."""
    pub = load("content/ch2_publish.json", {"videos": []})
    shorts = load("content/ch2_shorts.json", {"shorts": {}})
    pool = load("content/ch2_shorts/scripts.json", [])
    return {
        "channel": "Farmmer — ธรรมะก่อนนอน (@farmmer-n9t), Thai sleep/dharma niche",
        "live_long": [v.get("video_id") for v in pub["videos"] if v.get("video_id")],
        "shorts_live": len(shorts["shorts"]),
        "shorts_pool": len(pool),
        "as_of": datetime.now(timezone.utc).isoformat(timespec="minutes"),
    }


def ask(key: str, model: str, prompt: str) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
           f":generateContent?key={key}")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.7}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as fh:
            return json.load(fh)["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as exc:
        return f"GEMINI ERROR {exc.code}: {exc.read().decode()[:300]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", help="what to ask")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-state", action="store_true", help="ask without the channel facts")
    ap.add_argument("--extra", default="", help="extra facts to include")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set")

    parts = []
    if not args.no_state:
        parts.append("ข้อมูลจริงของช่องตอนนี้:\n" + json.dumps(channel_state(), ensure_ascii=False, indent=2))
    if args.extra:
        parts.append("ข้อมูลเพิ่มเติม:\n" + args.extra)
    parts.append("คำถาม: " + args.question)
    parts.append("ตอบเป็นภาษาไทย กระชับ ตรงประเด็น ระบุว่าอะไรควรทำก่อน-หลัง "
                 "ถ้ามีตัวเลขให้อ้างอิง และบอกชัดว่าอะไร *ไม่* ควรทำเพราะอะไร")
    print(ask(key, args.model, "\n\n".join(parts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
