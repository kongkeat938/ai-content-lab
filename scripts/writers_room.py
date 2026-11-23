#!/usr/bin/env python3
"""Several writers answer one brief, then a gate that can FAIL picks the usable ones.

K (2026-11-23): "ทีมที่ปรึกษาเรามีหลายตัวให้ลองเขียนบทได้ไหม เผื่อหลากหลายไอเดียขึ้น"
-- so the advisors stop being only reviewers and become a writing room: the same
brief goes to every writer that answers, and each draft is judged by the Shorts
spec it has to satisfy, not by who wrote it.

    python3 scripts/writers_room.py --topic "ร่างกายที่เหนื่อยทั้งวัน สมควรได้รับการขอบคุณ"
    python3 scripts/writers_room.py --topic "..." --writers gemini-3.5,pollinations
    python3 scripts/writers_room.py --topic "..." --out content/ch2_shorts/ideas.json

A draft is usable only when it parses as the Shorts shape, speaks for 35-45 s,
carries no bare digit (edge-tts reads a digit wrong), no emoji, and its hook is
not a near-copy of one already published. Everything else is reported with the
reason it was dropped -- a writer that fails is a measurement, not a silent skip.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import advise  # noqa: E402

MIN_CHARS, MAX_CHARS = 250, 700      # ~35-45 s of Thai narration
HOOK_HARD = 95                       # the real cap: the title is hook[:95] + " #Shorts"
HOOK_SOFT = 70                       # longer hooks read as a paragraph on a phone
NOVEL_FLOOR = 8                      # Thai runs are short; 3 chars matched everything

BRIEF = """คุณเป็นนักเขียนบท Shorts ภาษาไทยให้ช่อง "{channel}" ผู้ชมคือคนไทยวัย 35-65 ที่นอนไม่หลับ คิดมาก
น้ำเสียงอบอุ่น ช้า ๆ ห้ามขายของ ห้ามอ้างอิงงานวิจัย

เขียน 1 เรื่อง ยาว 35-45 วินาที (พูดประมาณ 90-110 คำ) ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{"hook": "ประโยคเปิด 1 บรรทัดที่ทำให้หยุดดู", "lines": ["ประโยคสั้น ๆ 6-8 บรรทัด"], "cta": "ชวนฟังคลิปเต็ม 1 บรรทัด"}}

หัวข้อ: {topic}
กติกา: ใช้คำไทยง่าย ๆ · ห้ามมีตัวเลขโดด (เขียนเป็นคำ) · ห้ามใช้ emoji · ทุกบรรทัดพูดออกเสียงได้จริง"""


def build_brief(topic: str, channel: str = "Farmmer ธรรมะก่อนนอน") -> str:
    return BRIEF.format(topic=topic, channel=channel)


def parse(text: str) -> dict | None:
    """Pull the JSON object out of a reply that may be fenced or chatty."""
    if not text or text.startswith("ERROR"):
        return None
    body = re.sub(r"```(?:json)?", "", text).strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        got = json.loads(body[start:end + 1])
    except json.JSONDecodeError:
        return None
    return got if isinstance(got, dict) else None


def problems(script: dict | None, existing_hooks: list[str] | None = None) -> list[str]:
    """Every reason this draft cannot be used. An empty list means it ships."""
    if not script:
        return ["not JSON"]
    out: list[str] = []
    hook = str(script.get("hook", "")).strip()
    lines = script.get("lines")
    cta = str(script.get("cta", "")).strip()
    if not hook:
        out.append("no hook")
    elif len(hook) > HOOK_HARD:
        out.append(f"hook {len(hook)} chars > {HOOK_HARD} (title truncates)")
    if not isinstance(lines, list) or not 5 <= len(lines) <= 10:
        out.append(f"lines must be a list of 5-10 (got "
                   f"{len(lines) if isinstance(lines, list) else type(lines).__name__})")
        lines = lines if isinstance(lines, list) else []
    if not cta:
        out.append("no cta")
    speech = hook + "".join(str(x) for x in lines) + cta
    if not MIN_CHARS <= len(speech) <= MAX_CHARS:
        out.append(f"speech {len(speech)} chars outside {MIN_CHARS}-{MAX_CHARS}")
    if re.search(r"[0-9]", speech):
        out.append("bare digit (edge-tts reads it wrong)")
    if re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", speech):
        out.append("emoji")
    stray = set(re.findall(r"[A-Za-z\u0400-\u04FF\u0E80-\u0EFF\u4E00-\u9FFF]", speech))
    if stray:
        out.append(f"non-Thai letters {''.join(sorted(stray))[:12]} (mixed-script gibberish)")
    for hook_seen in existing_hooks or []:
        if len(hook_seen) >= NOVEL_FLOOR and hook[:NOVEL_FLOOR] == hook_seen[:NOVEL_FLOOR]:
            out.append("hook repeats a published one")
            break
    return out


def existing_hooks(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    data = json.load(open(path, encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("scripts", [])
    return [str(s.get("hook", "")) for s in items if isinstance(s, dict)]


def ask(name: str, brief: str) -> tuple[str, float, str]:
    t0 = time.time()
    try:
        text = advise.ADVISORS[name](brief)
        return name, round(time.time() - t0, 1), text
    except Exception as exc:                                   # noqa: BLE001
        return name, round(time.time() - t0, 1), f"ERROR: {type(exc).__name__}: {exc}"[:200]


def rank(rows: list[dict], judge: str = "gemini-3.5") -> dict[str, int]:
    """A second judge for what the mechanical gate cannot see: does the Thai read
    naturally, and would a tired viewer keep watching? Scores, never invents."""
    drafts = "\n\n".join(f"[{r['writer']}]\n{json.dumps(r['script'], ensure_ascii=False)}"
                         for r in rows)
    prompt = ("ให้คะแนนบท Shorts ภาษาไทยต่อไปนี้ทีละบท ในฐานะผู้ชมวัย 35-65 ที่นอนไม่หลับ "
              "เกณฑ์: ภาษาไทยเป็นธรรมชาติ (ไม่ใช่ประโยคแปล), น้ำเสียงอบอุ่น ช้า ๆ, "
              "hook ทำให้หยุดดู, ทำตามสัจจะ 35-45 วินาที\n"
              'ตอบเป็น JSON เท่านั้น: {"<ชื่อผู้เขียน>": <คะแนนเต็ม 10>}\n\n' + drafts)
    got = parse(advise.ADVISORS[judge](prompt)) or {}
    return {k: int(v) for k, v in got.items() if isinstance(v, (int, float))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--channel", default="Farmmer ธรรมะก่อนนอน")
    ap.add_argument("--writers", default="gemini-3.5,gemini-3.1,pollinations,openhands-gpt",
                    help="comma list of advisor names (see advise.ADVISORS)")
    ap.add_argument("--seen", default=os.path.join(HERE, "..", "content", "ch2_shorts", "scripts.json"))
    ap.add_argument("--out", help="write the usable drafts here as JSON")
    ap.add_argument("--timeout", type=float, default=150.0, help="per writer, seconds")
    ap.add_argument("--judge", default="gemini-3.5", help="who scores the survivors")
    ap.add_argument("--no-rank", action="store_true", help="skip the quality judge")
    a = ap.parse_args()

    names = [n.strip() for n in a.writers.split(",") if n.strip()]
    unknown = [n for n in names if n not in advise.ADVISORS]
    if unknown:
        sys.exit(f"unknown writer(s): {unknown}; known: {sorted(advise.ADVISORS)}")
    brief = build_brief(a.topic, a.channel)
    seen = existing_hooks(os.path.abspath(a.seen))

    rows = []
    with cf.ThreadPoolExecutor(max_workers=len(names)) as ex:
        futs = {ex.submit(ask, n, brief): n for n in names}
        try:
            for fut in cf.as_completed(futs, timeout=a.timeout + 10):
                name, secs, text = fut.result()
                script = parse(text)
                bad = problems(script, seen)
                rows.append({"writer": name, "secs": secs, "script": script,
                             "problems": bad, "raw": text})
        except cf.TimeoutError:
            # A slow writer is a result too: report the ones that answered.
            for fut, name in futs.items():
                if fut.done() and not any(r["writer"] == name for r in rows):
                    got_name, secs, text = fut.result()
                    rows.append({"writer": got_name, "secs": secs, "script": parse(text),
                                 "problems": problems(parse(text), seen), "raw": text})
                elif not fut.done():
                    rows.append({"writer": name, "secs": a.timeout, "script": None,
                                 "problems": [f"no answer in {a.timeout:.0f}s"], "raw": ""})

    rows.sort(key=lambda r: (len(r["problems"]), r["secs"]))
    print(f"\nbrief: {a.topic}\n{'writer':18} {'secs':>6} {'chars':>6}  verdict")
    for r in rows:
        s = r["script"] or {}
        chars = len(str(s.get("hook", "")) + "".join(map(str, s.get("lines", []))) + str(s.get("cta", "")))
        verdict = "USABLE" if not r["problems"] else "; ".join(r["problems"])
        print(f"{r['writer']:18} {r['secs']:6} {chars:6}  {verdict}")

    usable = [r for r in rows if not r["problems"]]
    print(f"\n{len(usable)}/{len(rows)} usable")
    if usable and not a.no_rank:
        try:
            scores = rank(usable, a.judge)
        except Exception as exc:                               # noqa: BLE001
            scores = {}
            print(f"(judge unavailable: {type(exc).__name__}: {str(exc)[:60]})")
        if scores:
            print(f"\n{'writer':18} {'score':>5}  (judge: {a.judge})")
            for r in sorted(usable, key=lambda r: -scores.get(r["writer"], 0)):
                print(f"{r['writer']:18} {scores.get(r['writer'], 0):5}/10")
            usable.sort(key=lambda r: -scores.get(r["writer"], 0))
    if a.out and usable:
        payload = [{"writer": r["writer"], "topic": a.topic, "script": r["script"]} for r in usable]
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        print(f"wrote {a.out}")
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
