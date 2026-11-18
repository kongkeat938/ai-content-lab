#!/usr/bin/env python3
"""When a build fails a quality gate, ask Gemini how to fix it -- and follow that.

K (2026-11-18): *"คุณภาพงานที่ไม่ผ่าน เอาไปถาม gemini เลย"*. So a failing gate does
not just veto and stop; it hands Gemini the measured reasons plus the artifact and
gets back a concrete fix. K's standing rule is then *"ต้องทำตามคำสั่งและแนะนำของ
gemini เมื่อติดปัญหา"* -- the fix is the instruction for the next build, not advice
to weigh.

Three rules this tool holds to:

1. **The gate's verdict is never changed by the fix.** A veto is a measurement; an
   LLM is not a primary source. This only *adds* a fix artifact. The build stays
   held until the fix is applied and re-measured.
2. **A dead Gemini must not break the gate.** If the call fails, `fix()` returns
   `ok=False` with the error and the gate carries on vetoing. No false pass.
3. **The fix is a file, so it survives the run.** Written to `content/fixes/`, so
   the next build (or a human) reads it. Free: `ask_gemini` uses the free
   GEMINI_API_KEY already wired into the rails.

    python3 scripts/fix_with_gemini.py --kind shorts_script --in content/ch2_shorts/scripts.json \
        --key 07 --reasons "hook 41s, over the 30s ceiling"
    python3 scripts/fix_with_gemini.py --kind manifest_entry --in content/ch2_publish.json \
        --key night_120 --reasons "longest card holds 9.0 min, over the 8 min limit"

The `fix()` core takes an injectable `ask` so a test can run it with no network.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX_DIR = os.path.join(ROOT, "content", "fixes")

# The house standard a fix must respect, so Gemini does not "fix" a Short by making
# it landscape or a long-form by making it a single static card.
HOUSE = (
    "มาตรฐานของช่อง (ห้ามละเมิดตอนแก้):\n"
    "- Shorts: 9:16 1080x1920, yuv420p tv/bt709, -14 LUFS, ยาว <= 60 วินาที, "
    "hook ต้องสั้น (<= 30 วินาทีสำหรับคลิปยาว, hook 20 วินาทีแรกของ Shorts)\n"
    "- Long-form: 1080p crf18, yuv420p tv/bt709, -14 LUFS, ภาพต้องเปลี่ยนเป็นช่วง ๆ "
    "(การ์ดหนึ่งใบห้ามยาวเกิน 8 นาที)\n"
    "- เปิดเรื่องด้วย hook ที่ดึงคนในไม่กี่วินาที ตรงกลุ่มผู้ชมไทย"
)


def build_prompt(kind: str, payload, reasons: list[str]) -> str:
    """The exact brief sent to Gemini. Every reason must appear (a fix that ignores
    a measured failure is not a fix), so the caller's reasons are listed verbatim."""
    why = "\n".join(f"- {r}" for r in reasons) or "- (ไม่ระบุ)"
    return (
        f"งานชิ้นนี้ 'ไม่ผ่าน' การตรวจคุณภาพ ({kind}) เหตุผลที่วัดได้:\n{why}\n\n"
        f"เนื้อหางาน:\n{json.dumps(payload, ensure_ascii=False, indent=2)[:6000]}\n\n"
        f"{HOUSE}\n\n"
        "สั่งงาน: แก้ให้ผ่านทุกเหตุผลข้างบน ตอบเป็นภาษาไทย กระชับ\n"
        "1) บอกสาเหตุที่แท้จริงและจุดที่ต้องแก้ (เป็นข้อ ๆ)\n"
        "2) ให้ของที่แก้แล้วพร้อมใช้ (สำหรับสคริปต์: hook/lines/cta ที่แก้แล้ว)\n"
        "ห้ามอธิบายยาว ห้ามแก้เรื่องที่ไม่เกี่ยวกับเหตุผลที่ให้มา"
    )


def _parse_script(text: str):
    """Pull a {hook,lines,cta} object out of Gemini's reply, or None."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except ValueError:
                        break
                    if isinstance(obj, dict) and {"hook", "lines"} <= set(obj):
                        return obj
                    break
        start = text.find("{", start + 1)
    return None


def fix(kind: str, payload, reasons: list[str], key: str = "", ask=None) -> dict:
    """Ask Gemini to fix a failed artifact. Never raises: a dead advisor is recorded,
    so the gate that called this keeps its veto.

    Returns {"ok", "advisor", "kind", "key", "reasons", "prompt", "fix_text",
    "script"(opt), "at"}. `ok` is True only when Gemini answered.
    """
    if ask is None:
        sys.path.insert(0, HERE)
        import advise  # noqa: PLC0415 - local module
        ask = advise.ask_gemini
    prompt = build_prompt(kind, payload, reasons)
    out = {
        "ok": False, "advisor": "gemini", "kind": kind, "key": key,
        "reasons": list(reasons), "prompt": prompt, "fix_text": "",
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        text = (ask(prompt) or "").strip()
    except Exception as exc:  # noqa: BLE001 - a dead advisor must not break the gate
        out["error"] = str(exc)[:300]
        return out
    if not text:
        out["error"] = "empty reply"
        return out
    out["ok"] = True
    out["fix_text"] = text
    if kind == "shorts_script":
        script = _parse_script(text)
        if script:
            out["script"] = script
    return out


def save(result: dict) -> str:
    """Write the fix where the next build (or a human) reads it. Returns the path."""
    os.makedirs(FIX_DIR, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    name = f"{result['kind']}_{result.get('key') or stamp}.json"
    path = os.path.join(FIX_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    return path


def _load(path: str, key: str):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        for item in data:
            if str(item.get("id")) == str(key):
                return item
        return {}
    if isinstance(data, dict) and "videos" in data:
        for item in data["videos"]:
            if str(item.get("key")) == str(key):
                return item
        return {}
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True,
                    choices=["shorts_script", "manifest_entry", "text"])
    ap.add_argument("--in", dest="src", default="", help="JSON file holding the artifact")
    ap.add_argument("--key", default="", help="id/key inside the file")
    ap.add_argument("--reasons", required=True, help="measured reasons, '; '-separated")
    ap.add_argument("--save", action="store_true", help="write content/fixes/<name>.json")
    a = ap.parse_args()

    payload = _load(a.src, a.key) if a.src else a.reasons
    reasons = [r.strip() for r in a.reasons.split(";") if r.strip()]
    r = fix(a.kind, payload, reasons, key=a.key)
    print(f"### {r['advisor']}  (ok={r['ok']})", flush=True)
    print(r.get("fix_text") or f"(unavailable: {r.get('error')})")
    if r.get("script"):
        print("\n--- usable script ---")
        print(json.dumps(r["script"], ensure_ascii=False, indent=2))
    if a.save:
        print(f"\nsaved: {save(r)}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
