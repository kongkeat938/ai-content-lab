#!/usr/bin/env python3
"""Collect competitor data from YouTube for each of our three niches."""
from __future__ import annotations
import json, sys, time
sys.path.insert(0, "work/research")
from yt import get

QUERIES = {
    "ch1_philosophy": [
        "ปรัชญาชีวิต", "ข้อคิดชีวิต", "ปรัชญาใช้ชีวิต", "ข้อคิดคนสำเร็จ",
    ],
    "ch2_dharma": [
        "ธรรมะก่อนนอน", "สวดมนต์ก่อนนอน", "ธรรมะสอนใจ", "นิทานธรรมะ",
    ],
    "ch4_story": [
        "นิทานไทย", "เรื่องเล่าก่อนนอน", "การ์ตูนนิทานไทย", "ละครเสียงไทย",
    ],
}

out = {"videos": {}, "channels": {}}
seen_videos = {}

def search(q, order, n=15):
    return get("ch2", "search", {
        "part": "snippet", "q": q, "type": "video", "maxResults": n,
        "order": order, "relevanceLanguage": "th", "regionCode": "TH",
    })

for niche, qs in QUERIES.items():
    out["videos"][niche] = []
    for q in qs:
        for order in ("viewCount", "relevance"):
            try:
                d = search(q, order)
            except SystemExit as e:
                print("search fail", q, e); continue
            for it in d.get("items", []):
                vid = it["id"]["videoId"]; sn = it["snippet"]
                if vid in seen_videos:
                    continue
                seen_videos[vid] = True
                out["videos"][niche].append({
                    "videoId": vid, "title": sn["title"],
                    "channelId": sn["channelId"], "channelTitle": sn["channelTitle"],
                    "publishedAt": sn["publishedAt"], "query": q,
                })
            time.sleep(0.2)
    print(niche, "videos:", len(out["videos"][niche]))

# unique channels
chan_ids = sorted({v["channelId"] for niche in out["videos"] for v in out["videos"][niche]})
print("unique channels:", len(chan_ids))

# channel stats
for i in range(0, len(chan_ids), 50):
    chunk = chan_ids[i:i+50]
    d = get("ch2", "channels", {"part": "snippet,statistics,contentDetails,brandingSettings", "id": ",".join(chunk)})
    for it in d.get("items", []):
        s = it["statistics"]
        out["channels"][it["id"]] = {
            "title": it["snippet"]["title"],
            "subs": int(s.get("subscriberCount", 0)),
            "videos": int(s.get("videoCount", 0)),
            "views": int(s.get("viewCount", 0)),
            "published": it["snippet"]["publishedAt"][:10],
            "country": it["snippet"].get("country"),
            "uploads": it["contentDetails"]["relatedPlaylists"].get("uploads"),
            "keywords": (it.get("brandingSettings", {}).get("channel", {}) or {}).get("keywords", ""),
            "description": it["snippet"].get("description", "")[:300],
        }

# video stats for collected videos
vid_ids = list(seen_videos)
print("videos to stat:", len(vid_ids))
for i in range(0, len(vid_ids), 50):
    chunk = vid_ids[i:i+50]
    d = get("ch2", "videos", {"part": "statistics,contentDetails,snippet", "id": ",".join(chunk)})
    for it in d.get("items", []):
        st = it["statistics"]; cd = it["contentDetails"]
        out.setdefault("vstats", {})[it["id"]] = {
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "duration": cd["duration"],
            "publishedAt": it["snippet"]["publishedAt"][:10],
            "channelId": it["snippet"]["channelId"],
            "title": it["snippet"]["title"],
        }

with open("work/research/raw.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("wrote work/research/raw.json")
