#!/usr/bin/env python3
"""Vet a Shorts script with several AI models before it is rendered.

One model writes a draft; the same model can miss its own weak line. This asks a
panel to score the draft, list the weak points, and propose a revision, then
keeps the highest-scoring revision. It is the "many models filter the script"
step, and it runs from the pod with no browser.

Voters, measured 2026-11-04 on the free key: gemini-3.1-flash-lite and
gemini-3-flash-preview answer reliably, gemini-3.5-flash-lite intermittently
503s, and Pollinations (anonymous) is rate-limited to ~1 reply / 45 s and
truncates long JSON. gemini-2.5-* are retired (404) and gemma-* 500. Each voter
is independent, so a busy one lowers the panel's vote count, never its run.

    python3 scripts/panel_script.py --channel dharma --input draft.json
    python3 scripts/panel_script.py --channel dharma --input draft.json --rounds 2

Input is one script object: {"hook": "...", "lines": [...], "cta": "..."}.
Output is written next to it as <input>.panel.json with the chosen revision and
every vendor's vote, so the decision is auditable rather than a black box.

Vendors fail independently: if Gemini is overloaded the vote falls to
Pollinations, and vice versa. A run needs at least one vote to return a script.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# Independent voters. Several distinct models, so one model's blind spot is
# caught by another instead of a single model grading its own draft.
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
POLL_URL = "https://text.pollinations.ai/openai"

# The measured rule each channel's hook must satisfy, so a vendor is told what
# "good" means for this channel instead of guessing.
STYLE = {
    "dharma": {
        "name": "Farmmer — ธรรมะก่อนนอน",
        "audience": "คนไทยที่นอนไม่หลับ เครียด คิดมากตอนกลางคืน",
        "hook_rule": 'hook ต้องมีคำ "ลอง" หรือ "คืนนี้" หรือ "เปิดทิ้งไว้" และบอกสิ่งที่ทำได้จริงคืนนี้',
        "measured": "ฮุกที่บอกให้ลงมือทำได้ 300-570 วิว/วัน; ฮุกที่ทวนปัญหา 74-173 วิว/วัน",
    },
    "genx": {
        "name": "ตาต้า GenX — ปรัชญาชีวิต",
        "audience": "คนไทยวัยผู้ใหญ่ที่เหนื่อยกับชีวิต กำลังหาความหมาย",
        "hook_rule": 'hook ต้องมีคำ "มีสิทธิ์" หรือ "ไม่ต้อง" หรือ "อนุญาต" และให้การปลดปล่อย',
        "measured": "ฮุกแบบให้สิทธิ์ 310-373 วิว/วัน; ฮุกแบบทวนความจริงต่ำกว่ามาก",
    },
    "kongkeat-story": {
        "name": "เรื่องเล่าอบอุ่นใจ",
        "audience": "คนไทยที่ชอบเรื่องเล่าอบอุ่นใจ",
        "hook_rule": "hook ต้องเป็นช่วงเวลาครอบครัวที่เจาะจง มีความสัมพันธ์ (พ่อ/แม่/พี่) + การกระทำทางกาย",
        "measured": "ช่วงเวลาครอบครัวเจาะจง 460-1083 วิว; เรื่องคลาสสิก 1-6 วิว",
    },
}


def _gemini(prompt: str, key: str, model: str) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json"}}).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=90) as fh:
        return json.load(fh)["candidates"][0]["content"]["parts"][0]["text"]


def _pollinations(prompt: str) -> str:
    # Anonymous tier: the reasoning model overruns its output tokens unless the
    # effort is capped, and it allows only ~1 reply / 45 s per IP. So ask once
    # with a low effort cap; on any limit, skip rather than stall the whole run.
    body = json.dumps({"model": "openai", "reasoning_effort": "low", "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(POLL_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as fh:
        return json.load(fh)["choices"][0]["message"]["content"]


def _json_block(text: str) -> dict:
    """Pull the first JSON object out of a vendor reply (some wrap it in prose)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _rubric(slug: str, script: dict) -> str:
    s = STYLE[slug]
    return f"""คุณเป็นบรรณาธิการสคริปต์ Shorts ไทยให้ช่อง "{s['name']}" กลุ่มเป้าหมาย: {s['audience']}
กติกาฮุกของช่องนี้: {s['hook_rule']} (หลักฐานวัดจริง: {s['measured']})
กติกาเนื้อหา: lines 8-9 บรรทัด บรรทัดละ 6-12 คำ, ห้ามมีเลขอารบิก/เลขไทย, ไม่มี emoji,
ต้องมี "หนึ่งสิ่งที่ทำได้จริง" และทิ้งปมให้ไปดูคลิปยาว

สคริปต์ที่ต้องตรวจ:
{json.dumps(script, ensure_ascii=False, indent=2)}

ให้คะแนน 0-100 และชี้จุดอ่อน แล้วเสนอฉบับแก้ที่ "ดีที่สุด"
ตอบเป็น JSON เท่านั้น รูปแบบ:
{{"score": <0-100>, "issues": ["..."], "revised": {{"hook": "...", "lines": ["...", "..."], "cta": "..."}}}}"""


def vet(slug: str, script: dict, key: str) -> list:
    """Ask every reachable voter for a score + revision. Returns one vote each."""
    prompt = _rubric(slug, script)
    voters = [(f"gemini:{m}", (lambda p, m=m: _gemini(p, key, m))) for m in GEMINI_MODELS]
    voters.append(("pollinations", _pollinations))
    votes = []
    for name, fn in voters:
        try:
            v = _json_block(fn(prompt))
            if isinstance(v.get("revised"), dict):
                v["vendor"] = name
                votes.append(v)
                print(f"  {name}: score={v.get('score')} issues={len(v.get('issues', []))}")
            else:
                print(f"  {name}: reply had no revision -- skipped")
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: unavailable ({type(e).__name__}: {str(e)[:50]})")
    return votes


def _shape_ok(s: dict) -> bool:
    return (isinstance(s, dict) and s.get("hook") and isinstance(s.get("lines"), list)
            and len(s["lines"]) >= 3 and s.get("cta")
            and not re.search(r"[0-9๐-๙]", " ".join([s["hook"], *s["lines"], s["cta"]])))


def panel(slug: str, script: dict, rounds: int, key: str) -> dict:
    cur = script
    log = []
    for rnd in range(1, rounds + 1):
        print(f"round {rnd}: vets '{str(cur.get('hook'))[:40]}'")
        votes = vet(slug, cur, key)
        if not votes:
            log.append({"round": rnd, "votes": [], "note": "no vendor reachable"})
            break
        log.append({"round": rnd, "votes": votes})
        best = max(votes, key=lambda v: v.get("score") or 0)
        rev = best.get("revised")
        if _shape_ok(rev):
            cur = {"hook": rev["hook"], "lines": rev["lines"], "cta": rev["cta"]}
            print(f"  -> took {best['vendor']}'s revision (score {best.get('score')})")
        else:
            print("  -> no valid revision this round; keeping current")
    return {"chosen": cur, "rounds": log}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, choices=sorted(STYLE))
    ap.add_argument("--input", required=True, help="script JSON file")
    ap.add_argument("--out", help="output path (default <input>.panel.json)")
    ap.add_argument("--rounds", type=int, default=2)
    a = ap.parse_args()
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        sys.exit("GEMINI_API_KEY is not set")
    script = json.load(open(a.input, encoding="utf-8"))
    if isinstance(script, list):
        script = script[0]
    out = a.out or a.input + ".panel.json"
    result = panel(a.channel, script, a.rounds, key)
    result["channel"] = a.channel
    result["input"] = a.input
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nchosen hook: {result['chosen']['hook']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
