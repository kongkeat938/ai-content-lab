#!/usr/bin/env python3
"""Turn a finished night-compilation release into a publish-manifest entry.

The gap this closes: the night rail built a verified 120-minute file, attached it
to a GitHub Release, and stopped. Making it live needed a hand-written entry in
content/ch2_publish.json, so the watch-hour lever sat idle between builds. This
writes that entry automatically, right after the release is created, so the
existing publish-batch job (which triggers on a manifest push) uploads it.

Idempotent: an existing key keeps its video_id and state; only the URLs, duration
and cover are refreshed. That means a weekly rebuild of the same content updates
the entry instead of duplicating it, and a re-run never re-uploads.

    python3 scripts/add_release_to_manifest.py \
        --tag night-abc123 --key night_theme_x \
        --content content/night_dharma_02 --minutes 120 \
        --title "ธรรมะก่อนนอน 120 นาที ..." --receipt work/night/receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = "kongkeat938/ai-content-lab"
NIGHT_TAGS = ["ธรรมะก่อนนอน", "ฟังธรรมะก่อนนอน", "เสียงธรรมะนอนหลับ", "ธรรมะผ่อนคลาย",
              "แก้โรคนอนไม่หลับ", "ลดความเครียด", "นั่งสมาธิก่อนนอน", "ปล่อยวาง",
              "ทำใจให้สงบ", "นอนหลับสบาย"]


def release_url(tag: str, asset: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{tag}/{asset}"


def read_receipt(path: str) -> dict:
    """Prefer the local receipt (exact numbers); fall back to the .info.json the
    compilation writes beside the audio."""
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def duration_of(receipt: dict, content: str, minutes: float) -> float:
    ai = receipt.get("audio_info") or {}
    if ai.get("duration_sec"):
        return float(ai["duration_sec"])
    info = os.path.join(ROOT, "work", "night", "compilation.mp3.info.json")
    if os.path.exists(info):
        with open(info, encoding="utf-8") as fh:
            return float(json.load(fh).get("duration_sec", minutes * 60))
    return float(minutes * 60)


def make_cover(key: str, title: str, image: str, cover_dir: str) -> str:
    """Build a 1280x720 cover from a poster image so the upload has a real
    thumbnail. Best-effort: a missing Pillow is not fatal."""
    out = os.path.join(ROOT, cover_dir, f"{key}.jpg")
    try:
        from PIL import Image
        os.makedirs(os.path.dirname(out), exist_ok=True)
        sys.path.insert(0, HERE)
        import make_poster  # noqa: E402
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            big = os.path.join(tmp, "big.jpg")
            make_poster.build(image, big, title, "", 6, "", "")
            Image.open(big).convert("RGB").resize((1280, 720), Image.LANCZOS).save(out, quality=88)
        return os.path.relpath(out, ROOT)
    except Exception as exc:  # noqa: BLE001
        print(f"  cover not built ({exc}); the upload will use the channel default")
        return ""


def description_for(title: str, minutes: int, content: str) -> str:
    names = []
    if os.path.isdir(content):
        for f in sorted(os.listdir(content)):
            if f.endswith(".txt"):
                names.append(re.sub(r"^\d+_", "", f[:-4]))
    topics = " · ".join(names[:10])
    return (f"ฟังเสียงบรรยายธรรมะก่อนนอน {minutes} นาที ช่วยกล่อมจิตใจให้สงบ "
            f"ปล่อยวางเรื่องกังวลและความเครียดสะสมทั้งวัน เหมาะกับคนที่นอนไม่หลับและคิดมากตอนกลางคืน\n\n"
            f"เปิดทิ้งไว้ได้ทั้งคืน ไม่ต้องเพ่ง ไม่ต้องตั้งใจ แค่หลับตาฟังเสียงเบา ๆ ไปพร้อมลมหายใจ\n\n"
            f"บทที่ผ่านมา: {topics}\n\n"
            f"ฝากกดติดตามช่อง Farmmer — ธรรมะก่อนนอน เพื่อรับคลิปกล่อมใจทุกคืน ขอให้คืนนี้เป็นคืนที่ใจได้พัก\n\n"
            f"— ช่องพี่น้อง —\nเรื่องเล่าอบอุ่นใจ — ความทรงจำครอบครัว\n"
            f"https://www.youtube.com/channel/UC7gCIu4G_7QCEJ8hJ-34zoQ")


def story_description(title: str, minutes: int, content: str) -> str:
    names = []
    if os.path.isdir(content):
        for f in sorted(os.listdir(content)):
            if f.endswith(".txt"):
                names.append(re.sub(r"^\d+_", "", f[:-4]))
    topics = " · ".join(names[:10])
    return (f"รวมเรื่องเล่าอบอุ่นใจจากครอบครัวไทย — พ่อ แม่ พี่ ยาย ตา — เล่าด้วยเสียงนุ่ม ๆ "
            f"ต่อเนื่อง {minutes} นาที ฟังเพลินได้ทั้งคืน\n\n"
            f"แต่ละตอนเป็นช่วงเวลาง่าย ๆ ที่ทุกบ้านมี แล้วจำได้ไม่ลืม\n\n"
            f"ตอนในคลิปนี้: {topics}\n\n"
            f"ฝากกดติดตามช่อง เรื่องเล่าอบอุ่นใจ เพื่อรับเรื่องเล่าอบอุ่นใจใหม่ทุกสัปดาห์\n\n"
            f"— ช่องพี่น้อง —\nFarmmer — ธรรมะก่อนนอน\n"
            f"https://www.youtube.com/channel/UCM3QO5L_pmj34n1JVlbhh-w")


def philosophy_description(title: str, minutes: int, content: str) -> str:
    names = []
    if os.path.isdir(content):
        for f in sorted(os.listdir(content)):
            if f.endswith(".txt"):
                names.append(re.sub(r"^\d+_", "", f[:-4]))
    topics = " · ".join(names[:10])
    return (f"รวมข้อคิดและปรัชญาชีวิตสำหรับคนวัยทำงาน {minutes} นาที "
            f"ฟังเพลิน ๆ ช่วยให้ใจสงบ ได้มุมมองใหม่กับเรื่องที่แบกมาทั้งวัน\n\n"
            f"เปิดฟังได้ทุกเวลา ทั้งตอนพัก ตอนขับรถ หรือก่อนนอน "
            f"ไม่ต้องเพ่ง ไม่ต้องตั้งใจ แค่ฟังเสียงนุ่ม ๆ ไปเรื่อย ๆ\n\n"
            f"ตอนในคลิปนี้: {topics}\n\n"
            f"ฝากกดติดตามช่อง ตาต้า GenX — ปรัชญาชีวิต เพื่อรับข้อคิดใหม่ ๆ ที่ช่วยให้ใจเบาลง\n\n"
            f"— ช่องพี่น้อง —\nFarmmer — ธรรมะก่อนนอน\n"
            f"https://www.youtube.com/channel/UCM3QO5L_pmj34n1JVlbhh-w")


# Per-channel publish shape: tags, category, description builder, cover directory,
# and the long-form playlist a Short funnels to. Writing `playlist` here is what
# actually closes the funnel: publish_batch inserts the uploaded video into it, so
# the Shorts' tail link lands on a playlist that holds the video.
CHANNELS = {
    "dharma": {
        "tags": NIGHT_TAGS, "category_id": 22, "cover_dir": "assets/branding/farmmer/thumbs",
        "desc": description_for, "playlist": "PLBpZCGnd7Q5Y",
    },
    "genx": {
        "tags": ["ปรัชญาชีวิต", "ข้อคิดชีวิต", "แง่คิด", "กำลังใจ", "คนวัยทำงาน",
                 "ปล่อยวาง", "ความสุข", "รักตัวเอง", "คิดมาก", "จิตสงบ",
                 "ฟังเพลิน", "GenX", "ให้กำลังใจตัวเอง"],
        "category_id": 22, "cover_dir": "assets/branding/genx/thumbs",
        "desc": philosophy_description, "playlist": "PLXEV3B3DcgsU",
    },
    "kongkeat": {
        "tags": ["เรื่องเล่า", "เรื่องเล่าอบอุ่นใจ", "ครอบครัว", "เรื่องสั้น", "ฟังก่อนนอน",
                 "เรื่องเล่าภาษาไทย", "นิทานผู้ใหญ่", "คลิปกล่อมใจ", "เรื่องเล่าตอนเดียวจบ",
                 "ฟังเพลิน ๆ"],
        "category_id": 24, "cover_dir": "assets/branding/thumbs", "desc": story_description,
        "playlist": "PLU4aztRNvt28",
    },
}


def apply_qa_gate(entry: dict, receipt: dict) -> None:
    """Grade a finished build and set entry['state'] from the verdict.

    A blocked build is recorded but never uploaded (publish_batch skips
    state=blocked). Two guards, both learned the hard way (2026-11-09):

    * an EMPTY receipt means the build was skipped, not that the video is bad.
      grade({}) returns blocked (verdict is None) -- a false veto that stranded a
      verified video -- so with no receipt the state is left untouched.
    * a passing (re)grade must clear an earlier veto, or a fixed build stays
      blocked forever because the manifest hit still carries state=blocked.
    """
    if not receipt:
        print("  no receipt here (build was skipped); leaving the state unchanged")
        return
    try:
        sys.path.insert(0, HERE)
        import qa_gate  # noqa: E402
        qa = qa_gate.grade(receipt)
    except Exception as exc:  # noqa: BLE001 - a missing gate must not block the rail
        print(f"  QA gate skipped ({exc})")
        return
    entry["qa"] = qa
    if qa["blocked"] and not entry.get("video_id"):
        entry["state"] = "blocked"
        print(f"  QA VETO (grade {qa['grade']}): " + "; ".join(qa["reasons"]))
        return
    if not entry.get("video_id"):
        entry["state"] = "ready"
    print(f"  QA grade {qa['grade']} -- publishable")


def queue_entry(vids: list, entry: dict, receipt: dict) -> str:
    """Merge the freshly built entry into the manifest; return added|updated.

    Ordering matters: apply_qa_gate() must run BEFORE this, so a passing (re)grade
    clears an earlier veto. A prior hit's state and qa are copied into the entry
    only to preserve the upload record when the current run cannot re-grade -- a
    skipped build with no receipt. Otherwise the fresh verdict wins. Getting this
    backwards shipped state=blocked with qa=null over a fresh grade B (measured
    2026-11-09), because the gate then edited an entry no longer in the manifest.
    """
    hit = next((v for v in vids if v.get("key") == entry["key"]), None)
    if not hit:
        vids.append(entry)
        return "added"
    if "video_id" in hit:
        entry["video_id"] = hit["video_id"]
    if not receipt:
        entry["state"] = hit.get("state", entry.get("state", "ready"))
        if "qa" in hit:
            entry["qa"] = hit["qa"]
    hit.update(entry)
    return "updated"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(ROOT, "content", "ch2_publish.json"))
    ap.add_argument("--channel", default="dharma", choices=list(CHANNELS))
    ap.add_argument("--tag", required=True, help="the release tag holding video.mp4")
    ap.add_argument("--key", required=True, help="manifest key, e.g. night_theme_x")
    ap.add_argument("--content", required=True, help="content dir, for the description")
    ap.add_argument("--minutes", type=int, default=120)
    ap.add_argument("--title", required=True)
    ap.add_argument("--receipt", default="")
    ap.add_argument("--image", default="assets/images/img00_00.jpg")
    ap.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"])
    ap.add_argument("--not-before", default="", help="ISO time to hold the upload until")
    args = ap.parse_args()

    cfg = CHANNELS[args.channel]
    with open(args.manifest, encoding="utf-8") as fh:
        man = json.load(fh)
    vids = man.setdefault("videos", [])

    receipt = read_receipt(args.receipt)
    entry = {
        "key": args.key,
        "state": "ready",
        "video_url": release_url(args.tag, "video.mp4"),
        "audio_url": release_url(args.tag, "compilation.mp3"),
        "thumbnail": make_cover(args.key, args.title, args.image, cfg["cover_dir"]),
        "duration_sec": round(duration_of(receipt, args.content, args.minutes), 1),
        "title": args.title,
        "description": cfg["desc"](args.title, args.minutes, args.content),
        "tags": cfg["tags"],
        "category_id": cfg["category_id"],
        "privacy": args.privacy,
    }
    if cfg.get("playlist"):
        entry["playlist"] = cfg["playlist"]
    if args.not_before:
        entry["not_before"] = args.not_before

    apply_qa_gate(entry, receipt)
    action = queue_entry(vids, entry, receipt)

    with open(args.manifest, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
    live = entry.get("video_id", "")
    print(f"{action} {args.key} in {os.path.relpath(args.manifest, ROOT)} "
          f"({entry['duration_sec']}s, privacy={entry['privacy']}"
          f"{', already live ' + live if live else ''})")
    print(f"  created {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
