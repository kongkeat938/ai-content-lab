"""Run the next MV end to end: fresh art -> gate -> manifest -> upload -> stamp.

`make_mv.py` builds and gates one MV; this driver picks what the next one is
(next free id, a music bed no MV has used, a title no MV has used), so the
series can be run again and again without a human choosing anything and
without ever repeating a picture (the ledger in `make_mv.py` enforces that).

Usage:
    python3 mv_run.py [--channel dharma] [--minutes 60] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

LEDGER = os.path.join(ROOT, "content", "art_ledger_mv.json")
MANIFEST = {"dharma": "content/ch2_publish.json", "genx": "content/ch1_publish.json"}
THUMBS = {"dharma": "assets/branding/farmmer/thumbs", "genx": "assets/branding/genx/thumbs"}
CATEGORY = {"dharma": "10", "genx": "10"}
TITLES = {
    "dharma": [
        ("เพลงธรรมะบรรเลง 1 ชั่วโมง", "ฟังก่อนนอน ใจสงบ"),
        ("เพลงสมาธิบรรเลง 1 ชั่วโมง", "นั่งสมาธิ ผ่อนคลาย"),
        ("เพลงกล่อมนอน 1 ชั่วโมง", "หลับลึก ตื่นมาใจเบา"),
        ("เพลงธรรมชาติกับสมาธิ 1 ชั่วโมง", "ฟังตอนเช้า ใจปลอดโปร่ง"),
        ("เพลงภาวนาบรรเลง 1 ชั่วโมง", "ปล่อยวาง ใจสงบ"),
    ],
    "genx": [
        ("เพลงบรรเลงคิดงาน 1 ชั่วโมง", "โฟกัสเงียบ ๆ ไม่มีคำพูด"),
        ("เพลงอ่านหนังสือ 1 ชั่วโมง", "สมาธิยาว ไม่วอกแวก"),
    ],
}
DESC = """{title} {sub}

ไม่มีคำพูด ไม่มีโฆษณา — มีเพียงดนตรีเบา ๆ กับภาพเคลื่อนไหวช้า ๆ {n} ภาพ ที่เปลี่ยนไปเรื่อย ๆ

เปิดฟังได้ทุกเวลา ทั้งก่อนนอน ตอนอ่านหนังสือ ตอนทำงาน หรือตอนต้องการความสงบ

ฝากกดติดตามช่อง {channel} เพื่อรับคลิปใหม่ทุกวัน"""
TAGS = ["เพลงบรรเลง", "ฟังก่อนนอน", "สมาธิ", "ผ่อนคลาย", "ใจสงบ", "ดนตรีบำบัด",
        "เพลงกล่อมนอน", "ambient", "sleep music", "ธรรมะ"]
CHANNEL_NAME = {"dharma": "Farmmer — ธรรมะก่อนนอน", "genx": "ตาต้า GenX"}


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ledger() -> dict:
    with open(LEDGER, encoding="utf-8") as fh:
        return json.load(fh)


def plan(channel: str, ledger: dict) -> dict:
    day = time.strftime("%Y-%m-%d")
    n = 1 + sum(1 for k in ledger["mvs"] if k.startswith(f"mv_{day}_"))
    mv_id = f"mv_{day}_{n:02d}"
    used_music = {rec.get("music", {}).get("sha256") for rec in ledger["mvs"].values()}
    beds = sorted(os.path.join("assets", "music", f)
                  for f in os.listdir(os.path.join(ROOT, "assets", "music"))
                  if f.endswith(".mp3"))
    music = next((b for b in beds if sha(os.path.join(ROOT, b)) not in used_music), None)
    if music is None:
        raise SystemExit("FAIL: every music bed is already used by an MV")
    used_titles = {rec.get("title") for rec in ledger["mvs"].values()}
    titles = [f"{a} {b}" for a, b in TITLES[channel]]
    title = next((t for t in titles if t not in used_titles), None)
    if title is None:
        raise SystemExit(f"FAIL: every {channel} MV title is used; add one to TITLES")
    sub = ""
    for a, b in TITLES[channel]:
        if title == f"{a} {b}":
            sub = b
            break
    return {"mv_id": mv_id, "title": title, "sub": sub, "music": music,
            "out": os.path.join("work", "mv", f"{mv_id}.mp4")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="dharma", choices=sorted(MANIFEST))
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--images", type=int, default=12)
    ap.add_argument("--source", default="auto",
                    choices=["auto", "gemini", "pollinations", "procedural"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ledger = load_ledger()
    p = plan(a.channel, ledger)
    print(json.dumps(p, ensure_ascii=False, indent=2))
    if a.dry_run:
        return 0

    env = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"])
    subprocess.run([sys.executable, os.path.join(HERE, "make_mv.py"),
                    "--mv-id", p["mv_id"], "--style", a.channel, "--title", p["title"],
                    "--minutes", str(a.minutes), "--images", str(a.images),
                    "--source", a.source, "--music", p["music"], "--out", p["out"]],
                   check=True, env=env, stdin=subprocess.DEVNULL)

    thumb = os.path.join(THUMBS[a.channel], f"{p['mv_id']}.jpg")
    subprocess.run([sys.executable, os.path.join(HERE, "make_poster.py"),
                    os.path.join(ROOT, "assets", "art", "mv", p["mv_id"], "img01.jpg"),
                    thumb, "--title", p["title"], "--subtitle", p["sub"]],
                   check=True, env=env, stdin=subprocess.DEVNULL)

    mpath = os.path.join(ROOT, MANIFEST[a.channel])
    with open(mpath, encoding="utf-8") as fh:
        man = json.load(fh)
    man["videos"].append({
        "key": p["mv_id"], "state": "queued",
        "video_url": ("https://github.com/kongkeat938/ai-content-lab/releases/download/"
                      f"longform-{p['mv_id']}/video.mp4"),
        "thumbnail": thumb, "duration_sec": a.minutes * 60,
        "title": p["title"], "description": DESC.format(
            title=p["title"], sub=p["sub"], n=a.images, channel=CHANNEL_NAME[a.channel]),
        "tags": TAGS, "category_id": CATEGORY[a.channel], "privacy": "public",
        "built": time.strftime("%Y-%m-%dT%H:%M%z"),
        "note": "MV series: fresh sha-stamped art (content/art_ledger_mv.json)"})
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)

    token = {"dharma": "YT_CH2_REFRESH_TOKEN", "genx": "YT_CH1_REFRESH_TOKEN"}[a.channel]
    subprocess.run([sys.executable, os.path.join(HERE, "publish_batch.py"),
                    "--manifest", mpath, "--only", p["mv_id"],
                    "--cache", os.path.dirname(os.path.join(ROOT, p["out"])),
                    "--privacy", "public"],
                   check=True, env=dict(env, **{token: os.environ.get(token, "")}),
                   stdin=subprocess.DEVNULL)

    # The publish path records the id in the manifest; stamp it on the art ledger
    # so the image -> MV -> live video chain is one file.
    with open(mpath, encoding="utf-8") as fh:
        entry = next(v for v in json.load(fh)["videos"] if v["key"] == p["mv_id"])
    ledger = load_ledger()
    rec = ledger["mvs"][p["mv_id"]]
    rec["published"] = {"video_id": entry.get("video_id"), "url": entry.get("url"),
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "channel": a.channel}
    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2)
    import content_ledger as cl
    arc = cl.load()["videos"].get(p["mv_id"], {}).get("arc", "")
    cl.stamp(p["mv_id"], a.channel, [], title=p["title"], music=p["music"], arc=arc,
             url=rec["published"].get("url", ""), kind="music")
    print(f"LIVE: {rec['published']['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
