#!/usr/bin/env python3
"""Pull recent uploads from key competitors to measure cadence and current hits."""
from __future__ import annotations
import json, re, sys, time
sys.path.insert(0, "work/research")
from yt import get

def iso_to_sec(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m: return 0
    dd,hh,mm,ss = [int(x or 0) for x in m.groups()]
    return dd*86400+hh*3600+mm*60+ss

# Channel ids are resolved from raw.json by title, so collect.py must run first.
raw = json.load(open("work/research/raw.json", encoding="utf-8"))
byname = {v["title"]: cid for cid, v in raw["channels"].items()}
want = [
  "Dhamma Buddha 1 ปล่อยวาง", "ธรรมดี Channel", "เวสสะเศรษฐี", "อำพลธรรม",
  "PURIFILM channel", "hiphoplanla", "เล่านิทาน 3D",
  "Thai Fairy Tales", "DODI ดูดิ", "นิทานก่อนนอนสําหรับเด็ก",
  "THE STANDARD PODCAST", "Mission To The Moon", "Kru-Ngor ครูเงาะ รสสุคนธ์ กองเกตุ",
]
out = {}
for name in want:
    cid = byname.get(name)
    if not cid:
        print("not found:", name); continue
    ch = raw["channels"][cid]
    up = ch.get("uploads")
    if not up: 
        print("no uploads list:", name); continue
    ids = [it["contentDetails"]["videoId"] for it in
           get("ch2", "playlistItems",
               {"part": "contentDetails", "playlistId": up, "maxResults": 50}).get("items", [])]
    vids = []
    for i in range(0, len(ids), 50):
        vd = get("ch2", "videos", {"part": "statistics,contentDetails,snippet", "id": ",".join(ids[i:i+50])})
        for it in vd.get("items", []):
            st = it["statistics"]
            vids.append({
                "id": it["id"], "title": it["snippet"]["title"],
                "published": it["snippet"]["publishedAt"][:10],
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "sec": iso_to_sec(it["contentDetails"]["duration"]),
            })
    vids.sort(key=lambda v: v["published"], reverse=True)
    out[name] = {"channelId": cid, "subs": ch["subs"], "recent": vids}
    print(f"{name}: {len(vids)} recent")
    time.sleep(0.1)

json.dump(out, open("work/research/recent.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote recent.json")
