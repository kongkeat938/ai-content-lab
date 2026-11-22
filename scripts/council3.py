#!/usr/bin/env python3
"""Three-layer thinking council (K, 2026-11-22).

K measured five camps alive (pollinations, Gemini, KiloCode, G4FSpace, Yqcloud).
One call is one opinion; a decision needs three layers of thinking:

  L1 THINK  -- every vendor answers the same question plus the same measured
               facts, independently and in parallel. A vendor that fails is
               recorded by name, never silently dropped.
  L2 CHECK  -- every draft is critiqued by a DIFFERENT vendor against a fixed
               checklist (are its numbers in the facts? unsupported claims?
               logic? risk?). A draft that nobody critiques FAILS the run.
  L3 DECIDE -- one synthesizer gets the drafts and the critiques, and must answer
               in a fixed shape (DECISION / REASONS / NOT / CONFIDENCE / NUMBERS).
               A number >= 100 in the decision that is not in the supplied facts
               FAILS the run -- that is how an invented channel figure is caught.

Quorum and cross-check are real gates: fewer than `--min-vendors` answering, or a
panel too small to critique every draft, exits 2 (deferral) instead of pretending
the council decided.

    python3 scripts/council3.py "ควรทำอะไรต่อ" --extra "long-form 82.7 ชม./28 วัน"
    python3 scripts/council3.py "..." --vendors gemini,pollinations --json work/council.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import advise  # noqa: E402

# The five camps from K's table, plus the two extra Gemini models so a small
# panel still has an independent critic.
DEFAULT_VENDORS = ["gemini", "pollinations", "kilocode", "g4fspace", "yqcloud"]

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
YEAR = re.compile(r"^(19|20)\d\d$")

L1_SHAPE = (
    "ตอบเป็นภาษาไทย ไม่เกิน 12 บรรทัด ตามรูปแบบนี้เท่านั้น:\n"
    "สรุป: ...\nเหตุผล: 1) ... 2) ... 3) ...\nไม่ควรทำ: ...\n"
    "ตัวเลขที่ใช้: ... (ห้ามใช้ตัวเลขที่ไม่อยู่ใน FACTS)"
)
L2_SHAPE = (
    "ตรวจร่างนี้แบบเข้มงวด ตอบเป็นภาษาไทย ไม่เกิน 10 บรรทัด ตามรูปแบบนี้เท่านั้น:\n"
    "คะแนน: n/10\nตัวเลขที่ไม่มีใน FACTS: ...\nข้ออ้างที่ไม่มีหลักฐาน: ...\n"
    "ตรรกะที่ผิด: ...\nความเสี่ยง: ...\nควรแก้: ..."
)
L3_SHAPE = (
    "ตัดสินจากร่างและคำวิจารณ์ทั้งหมด ตอบเป็นภาษาไทย ตามรูปแบบนี้เท่านั้น:\n"
    "DECISION: ...\nREASONS: 1) ... 2) ... 3) ...\nNOT: ...\n"
    "CONFIDENCE: n/10\nNUMBERS: ... (คัดจาก FACTS เท่านั้น)"
)


def _prompt_layer1(question: str, facts: str) -> str:
    return f"QUESTION:\n{question}\n\nFACTS (วัดสด ใช้ได้เฉพาะตัวเลขที่อยู่ในนี้):\n{facts}\n\n{L1_SHAPE}"


def _prompt_layer2(question: str, facts: str, draft: str) -> str:
    return (f"QUESTION:\n{question}\n\nFACTS:\n{facts}\n\nร่างที่ต้องตรวจ:\n{draft}\n\n{L2_SHAPE}")


def _prompt_layer3(question: str, facts: str, drafts: dict, critiques: dict) -> str:
    blocks = [f"QUESTION:\n{question}", f"FACTS:\n{facts}"]
    for name, text in drafts.items():
        blocks.append(f"--- ร่างจาก {name} ---\n{text}")
    for draft_name, crit in critiques.items():
        blocks.append(f"--- วิจารณ์ร่าง {draft_name} (โดย {crit['by']}) ---\n{crit['text']}")
    blocks.append(L3_SHAPE)
    return "\n\n".join(blocks)


def ungrounded_numbers(text: str, facts: str) -> list[str]:
    """Numbers >= 100 (or with decimals) in `text` that are absent from `facts`.

    Small numbers are allowed (an answer may say "3 เหตุผล") and a year is not a
    measurement. Everything else must come from the facts we handed over.
    """
    allowed = {n.replace(",", "") for n in NUM.findall(facts)}
    bad: list[str] = []
    for raw in NUM.findall(text):
        norm = raw.replace(",", "")
        if norm in allowed:
            continue
        if YEAR.match(norm) and not raw.endswith("0.0"):
            continue
        try:
            value = float(norm)
        except ValueError:
            continue
        if value < 100 and "." not in raw:
            continue
        bad.append(raw)
    return bad


def _call(fn, prompt: str) -> tuple[str | None, str | None]:
    try:
        text = (fn(prompt) or "").strip()
        return (text, None) if text else (None, "empty reply")
    except Exception as exc:  # noqa: BLE001 - a dead vendor is data, not a crash
        return None, f"{type(exc).__name__}: {exc}"[:200]


def run(question: str, facts: str, vendors: dict, judge: str | None = None,
        min_vendors: int = 2, workers: int = 5) -> dict:
    """Run the three layers. `vendors` maps a name to callable(prompt) -> str."""
    if not vendors:
        raise ValueError("no vendors")
    out: dict = {"drafts": {}, "draft_errors": {}, "critiques": {},
                 "critique_errors": {}, "decision": "", "ungrounded": [],
                 "ok": False, "reason": ""}

    p1 = _prompt_layer1(question, facts)
    with ThreadPoolExecutor(max_workers=min(workers, len(vendors))) as ex:
        futures = {name: ex.submit(_call, fn, p1) for name, fn in vendors.items()}
        for name, fut in futures.items():
            text, err = fut.result()
            if text:
                out["drafts"][name] = text
            else:
                out["draft_errors"][name] = err

    if len(out["drafts"]) < min_vendors:
        out["reason"] = (f"quorum: {len(out['drafts'])}/{min_vendors} vendors answered "
                         f"(failed: {sorted(out['draft_errors'])})")
        return out
    if len(out["drafts"]) < 2:
        out["reason"] = "cross-check impossible: need 2 drafts from different vendors"
        return out

    alive = list(out["drafts"])
    pairs = []
    for i, author in enumerate(alive):
        critic = alive[(i + 1) % len(alive)]
        pairs.append((author, critic))
    p2 = {author: _prompt_layer2(question, facts, out["drafts"][author])
          for author, _ in pairs}
    with ThreadPoolExecutor(max_workers=min(workers, len(pairs))) as ex:
        futures = {author: ex.submit(_call, vendors[critic], p2[author])
                   for author, critic in pairs}
        for author, critic in pairs:
            text, err = futures[author].result()
            if text:
                out["critiques"][author] = {"by": critic, "text": text}
            else:
                out["critique_errors"][author] = {"by": critic, "error": err}

    if out["critique_errors"]:
        out["reason"] = f"a draft went uncriticised: {sorted(out['critique_errors'])}"
        return out

    judge_name = judge if judge in vendors else alive[0]
    text, err = _call(vendors[judge_name], _prompt_layer3(
        question, facts, out["drafts"], out["critiques"]))
    if not text:
        out["reason"] = f"judge {judge_name} failed: {err}"
        return out
    out["decision"] = text
    out["judge"] = judge_name
    out["ungrounded"] = ungrounded_numbers(text, facts)
    if out["ungrounded"]:
        out["reason"] = f"decision cites numbers absent from FACTS: {out['ungrounded']}"
        return out
    out["ok"] = True
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--extra", default="", help="measured facts to hand every vendor")
    ap.add_argument("--vendors", default="", help="comma list (default: the five camps)")
    ap.add_argument("--judge", default="", help="vendor that synthesises layer 3")
    ap.add_argument("--min-vendors", type=int, default=2)
    ap.add_argument("--json", default="", help="write the full three-layer record here")
    args = ap.parse_args()

    names = advise.resolve_team(
        [n.strip() for n in (args.vendors or ",".join(DEFAULT_VENDORS)).split(",") if n.strip()])
    vendors = {n: advise.advisor(n) for n in names}

    started = time.time()
    res = run(args.question, args.extra or "(ไม่มี)", vendors,
              judge=args.judge or None, min_vendors=args.min_vendors)
    res["elapsed_s"] = round(time.time() - started, 1)
    res["vendors"] = names

    print(f"== L1 THINK: {len(res['drafts'])}/{len(names)} answered")
    for name, text in res["drafts"].items():
        print(f"\n--- {name} ---\n{text}")
    for name, err in res["draft_errors"].items():
        print(f"!! {name}: {err}")
    print(f"\n== L2 CHECK: {len(res['critiques'])}/{len(res['drafts'])} drafts critiqued")
    for draft, crit in res["critiques"].items():
        print(f"\n--- {draft} ตรวจโดย {crit['by']} ---\n{crit['text']}")
    for draft, err in res["critique_errors"].items():
        print(f"!! {draft} ไม่มีคนตรวจ: {err}")
    if res["decision"]:
        print(f"\n== L3 DECIDE ({res.get('judge','')}) ==\n{res['decision']}")
    if res["ungrounded"]:
        print(f"\n!! ตัวเลขที่ไม่มีใน FACTS: {res['ungrounded']}")

    print(f"\nresult: {'OK' if res['ok'] else 'FAIL'} ({res['elapsed_s']}s)")
    if res["reason"]:
        print(f"reason: {res['reason']}")
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w") as fh:
            json.dump({"question": args.question, "facts": args.extra, **res},
                      fh, ensure_ascii=False, indent=2)
        print(f"wrote {args.json}")
    return 0 if res["ok"] else (2 if not res["decision"] else 1)


if __name__ == "__main__":
    sys.exit(main())
