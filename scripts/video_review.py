#!/usr/bin/env python3
"""Review the videos already on a channel and say how to improve them.

The question this answers: the analysis so far only *ranked* videos by views. It
never judged a video's quality or told anyone what to change. This tool does
both, from numbers the cloud can reach:

  * **Retention**  -- averageViewPercentage. >100% means people rewatched.
  * **Engagement** -- likes + comments + shares + subscribersGained per 1,000 views.
  * **Script**     -- for each video that matches a script in content/, the panel
                      reads the real hook/lines/cta and critiques it against the
                      channel's own best performers, then proposes a concrete edit.

It writes content/reviews/<channel>.json (per-video grade + fixes) and a readable
report. gen_short_scripts.py does not consume this directly; it is the learning
signal a human or the panel reads to sharpen the rules.

    python3 scripts/video_review.py --channel ch4
    python3 scripts/video_review.py --channel ch4 --panel --top 6
    python3 scripts/video_review.py --channel ch4 --panel --out docs/REVIEW-ch4.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOKEN_URL = "https://oauth2.googleapis.com/token"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
DATA = "https://www.googleapis.com/youtube/v3"

CHANNELS = {
    "ch1": ("YT_CH1_REFRESH_TOKEN", "content/ch1_shorts/scripts.json", "content/ch1_shorts.json"),
    "ch2": ("YT_CH2_REFRESH_TOKEN", "content/ch2_shorts/scripts.json", "content/ch2_shorts.json"),
    "ch3": ("YT_CH3_REFRESH_TOKEN", "", ""),
    "ch4": ("YT_CH4_REFRESH_TOKEN", "content/ch4_shorts/scripts.json", "content/ch4_shorts.json"),
}

METRICS = ("views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
           "likes,comments,shares,subscribersGained")

# Same alias map as studio_ai: one insights file serves both the channel id and
# the generator's name.
GEN_ALIAS = {"ch1": "genx", "ch2": "dharma", "ch4": "kongkeat-story"}


def access_token(env: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ[env], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as fh:
        return json.load(fh)["access_token"]


def report(tok: str, q: dict) -> dict:
    url = f"{ANALYTICS}?{urllib.parse.urlencode(q)}"
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"Authorization": f"Bearer {tok}"}), timeout=60) as fh:
        return json.load(fh)


def rows(d: dict) -> list[dict]:
    cols = [h["name"] for h in d.get("columnHeaders", [])]
    return [dict(zip(cols, r)) for r in d.get("rows", [])]


def titles_for(tok: str, ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(ids), 50):
        url = f"{DATA}/videos?part=snippet&id={','.join(ids[i:i + 50])}"
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"Authorization": f"Bearer {tok}"}), timeout=40) as fh:
                for it in json.load(fh).get("items", []):
                    out[it["id"]] = it["snippet"]["title"]
        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Daily quota is spent (resets 08:00 UTC). Titles are cosmetic; the
                # grades below still compute, so say so and carry on.
                print("  note: videos.list quota exhausted -- titles will fill in on "
                      "the next run after 08:00 UTC", file=sys.stderr)
            continue
    return out


def engagement_per_1k(r: dict) -> float:
    acts = sum(int(r.get(k, 0) or 0) for k in ("likes", "comments", "shares", "subscribersGained"))
    return round(acts / max(int(r.get("views", 0) or 1), 1) * 1000, 1)


def grade(r: dict, ret_med: float, eng_med: float) -> tuple[str, list[str]]:
    """Letter grade from retention and engagement against the channel's median."""
    notes: list[str] = []
    ret = float(r.get("averageViewPercentage", 0) or 0)
    eng = engagement_per_1k(r)
    score = 0
    if ret >= max(ret_med * 1.2, 60):
        score += 2; notes.append("retention สูงกว่าค่ากลางช่อง")
    elif ret >= ret_med:
        score += 1
    else:
        notes.append("retention ต่ำกว่าค่ากลางช่อง — ต้นคลิปอาจไม่ดึงพอ")
    if eng >= max(eng_med * 1.2, 1.0):
        score += 2; notes.append("engagement สูง")
    elif eng >= eng_med:
        score += 1
    else:
        notes.append("engagement ต่ำ — ไม่มีการกดใจ/คอมเมนต์/แชร์")
    return {0: "D", 1: "C", 2: "B", 3: "B+", 4: "A"}[min(score, 4)], notes


def load_manifest(rel: str) -> dict[str, str]:
    """Map video_id -> script id from the publish manifest (survives quota loss)."""
    if not rel:
        return {}
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        man = json.load(fh)
    out: dict[str, str] = {}
    for sid, rec in (man.get("shorts") or {}).items():
        vid = rec.get("video_id")
        if vid:
            out[vid] = sid
    return out


def match_script(title: str, scripts: list[dict]) -> dict | None:
    """Find the script whose hook best matches a video title (Thai: char bigrams)."""
    def bg(s: str) -> set[str]:
        s = "".join(ch for ch in s if not ch.isspace())
        return {s[i:i + 2] for i in range(len(s) - 1)}
    tb = bg(title)
    best, best_overlap = None, 0
    for s in scripts:
        ov = len(tb & bg(s.get("hook", "")))
        if ov > best_overlap:
            best, best_overlap = s, ov
    return best if best_overlap >= 4 else None


def ask_panel(items: list[dict]) -> dict[str, str]:
    sys.path.insert(0, HERE)
    import advise  # noqa: PLC0415
    lines = ["คลิปที่ทำผลงานดีที่สุดของช่อง (ใช้เป็นมาตรฐาน):"]
    for it in items:
        lines.append(f"  - {it['title']} | ดูจบ {it['averageViewPercentage']:.0f}% | "
                     f"engagement {it['eng']}/1k")
    lines.append("\nสคริปต์ที่ควรปรับปรุง (รายคลิป):")
    for it in items:
        sc = it.get("script")
        if not sc:
            continue
        lines.append(f"\n[{it['title']}] เกรด {it['grade']}")
        lines.append(f"  hook: {sc['hook']}")
        lines.append("  lines: " + " / ".join(sc["lines"][:9]))
        lines.append(f"  cta: {sc.get('cta','')}")
    q = ("จงวิจารณ์คุณภาพสคริปต์ Shorts ข้างบนแบบตรงไปตรงมา เป็นภาษาไทย:\n"
         "1) แต่ละคลิปมีจุดอ่อนอะไร (hook/lines/cta) เทียบกับคลิปที่ได้ผลดีสุด\n"
         "2) เขียน hook ใหม่ 1 บรรทัด + ปรับ lines ให้กระชับขึ้น สำหรับคลิปที่ควรแก้\n"
         "3) บรรทัดสุดท้าย ขึ้นต้นด้วย 'RULES:' แล้วเขียนกฎสั้น ๆ 3 ข้อที่ควรใช้กับทุกคลิป\n"
         "   ถัดไป คั่นแต่ละข้อด้วย ' | ' (กฎต้องเป็นคำสั่งที่ทำตามได้จริง)")
    payload = "\n".join(lines)
    out: dict[str, str] = {}
    for name in ("gemini", "pollinations"):
        fn = advise.ADVISORS.get(name)
        if not fn:
            continue
        try:
            out[name] = fn(f"{payload}\n\n{q}\n\n{advise.SYSTEM}").strip()
        except Exception as exc:  # noqa: BLE001
            out[name] = f"(unavailable: {str(exc)[:160]})"
    return out


def parse_rules(text: str) -> list[str]:
    """Pull the panel's forward-looking rules out of its answer."""
    for line in reversed(text.splitlines()):
        if "RULES:" in line:
            blob = line.split("RULES:", 1)[1]
            items = [t.strip(" -*\t") for t in blob.replace("|", "\n").splitlines()]
            return [t for t in items if 8 <= len(t) <= 160][:3]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="ch4", choices=sorted(CHANNELS))
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--top", type=int, default=6, help="how many videos to review in depth")
    ap.add_argument("--panel", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    env, scripts_path, manifest_path = CHANNELS[a.channel]
    tok = access_token(env)
    end = dt.date.today(); start = end - dt.timedelta(days=a.days)
    per_video = rows(report(tok, {"ids": "channel==MINE", "startDate": str(start),
        "endDate": str(end), "metrics": METRICS, "dimensions": "video",
        "sort": "-views", "maxResults": "50"}))
    names = titles_for(tok, [r["video"] for r in per_video])
    for r in per_video:
        r["title"] = names.get(r["video"], "(title unavailable)")
        r["eng"] = engagement_per_1k(r)

    ret_med = sorted(float(r["averageViewPercentage"]) for r in per_video)[len(per_video) // 2] if per_video else 0
    eng_med = sorted(r["eng"] for r in per_video)[len(per_video) // 2] if per_video else 0

    scripts: list[dict] = []
    if scripts_path and os.path.exists(os.path.join(ROOT, scripts_path)):
        with open(os.path.join(ROOT, scripts_path), encoding="utf-8") as fh:
            scripts = json.load(fh)
    by_id = {s["id"]: s for s in scripts}
    vid2sid = load_manifest(manifest_path)

    items = []
    for r in per_video[:a.top]:
        g, notes = grade(r, ret_med, eng_med)
        r["grade"], r["notes"] = g, notes
        # Prefer the manifest's exact script match; fall back to a title match when
        # the video is not in the manifest (e.g. a long-form upload).
        sid = vid2sid.get(r["video"])
        r["script"] = by_id.get(sid) if sid else match_script(r["title"], scripts)
        items.append(r)

    text = [f"# Video review — {a.channel} ({start}..{end})",
            f"ค่ากลางช่อง: ดูจบ {ret_med:.0f}% · engagement {eng_med:.1f}/1k\n",
            "| เกรด | วิว | ดูจบ% | eng/1k | คลิป |", "|---|---|---|---|---|"]
    for r in items:
        text.append(f"| {r['grade']} | {r['views']} | {r['averageViewPercentage']:.0f} | "
                    f"{r['eng']} | {r['title'][:52]} |")
    for r in items:
        text.append(f"\n**{r['title'][:60]}** — เกรด {r['grade']}")
        for n in r["notes"]:
            text.append(f"  - {n}")
        if r["script"]:
            text.append(f"  - hook: {r['script']['hook']}")

    answers: dict[str, str] = {}
    if a.panel:
        answers = ask_panel(items)
        for name, ans in answers.items():
            text.append(f"\n## panel: {name}\n{ans}")

    body = "\n".join(text)
    print(body)

    # Forward the panel's rules into the same insights file the generator reads,
    # so the next scripts are written under the critique -- a closed loop from
    # "what was weak" to "what to write differently".
    rules: list[str] = []
    for ans in answers.values():
        for r in parse_rules(ans):
            if r not in rules:
                rules.append(r)
        if rules:
            break

    rev_path = os.path.join(ROOT, "content", "reviews", f"{a.channel}.json")
    os.makedirs(os.path.dirname(rev_path), exist_ok=True)
    with open(rev_path, "w", encoding="utf-8") as fh:
        json.dump({"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "ret_median": round(ret_med, 1), "eng_median": eng_med,
                   "videos": [{k: r[k] for k in ("video", "title", "views", "averageViewPercentage",
                             "eng", "grade", "notes")} for r in items],
                   "rules": rules, "panel": answers}, fh, ensure_ascii=False, indent=1)
    print(f"\nwrote {rev_path}")

    if rules:
        for name in {a.channel, GEN_ALIAS.get(a.channel, a.channel)}:
            ip = os.path.join(ROOT, "content", "insights", f"{name}.json")
            if not os.path.exists(ip):
                continue
            with open(ip, encoding="utf-8") as fh:
                blob = json.load(fh)
            blob["rules"] = rules
            with open(ip, "w", encoding="utf-8") as fh:
                json.dump(blob, fh, ensure_ascii=False, indent=1)
        print(f"forwarded {len(rules)} rules to content/insights/")

    if a.out:
        path = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body + "\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
