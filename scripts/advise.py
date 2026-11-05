#!/usr/bin/env python3
"""Ask a panel of independent AI advisors one question and print every answer.

K's rule: never bring a decision to a person; take it to an AI. K also requires
**at least five advisors on every question** -- a single vendor is a single point
of failure (measured: ChatGPT's CDP route 404s, Gemini 503s, Pollinations 402s),
and one dead vendor must never stop a decision. This asks the whole panel and
reports which answered.

Advisors, in the order they are tried (all free, all measured working 2026-11-05):
  1. gemini           -- GEMINI_API_KEY (3.5/3.1-flash-lite/flash-lite-latest)
  2. pollinations     -- text.pollinations.ai/openai, no key
  3. openhands        -- OpenHands Cloud (KONGKEAT_OH_KEY), its own DeepSeek agent
  4. openhands-claude -- same key, llm_model=openhands/claude-sonnet-4-5
  5. openhands-gpt    -- same key, llm_model=openhands/gpt-5

The three OpenHands entries share one key but run genuinely different models, so
the panel is five independent opinions, not five copies of one. Each OpenHands
conversation is slow (~2-4 min), so the panel runs them last and in sequence.

    python3 scripts/advise.py "what should I change first?"
    python3 scripts/advise.py --extra "28-day: Shorts 30.3h, long-form 2.9h" "..."
    python3 scripts/advise.py --only gemini,pollinations "..."
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GEMINI_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest")
OH_BASE = os.environ.get("OPENHANDS_BASE_URL", "https://app.all-hands.dev")

SYSTEM = ("ตอบเป็นภาษาไทย กระชับ ตรงประเด็น ระบุว่าอะไรควรทำก่อน-หลัง "
          "ถ้ามีตัวเลขให้อ้างอิง และบอกชัดว่าอะไร *ไม่* ควรทำเพราะอะไร")


def _post(url: str, body: dict, headers: dict | None = None, timeout: int = 120):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers=headers or {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.load(fh)


def ask_gemini(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    last = ""
    for model in GEMINI_MODELS:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
               f":generateContent?key={key}")
        try:
            d = _post(url, {"contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.7}})
            return d["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as exc:
            last = f"{model}: HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 - try the next model
            last = f"{model}: {exc}"
    raise RuntimeError(last)


def ask_pollinations(prompt: str, tries: int = 3) -> str:
    # /openai returns the standard chat-completions JSON. The bare "/" path and
    # the GET path both fail on a long prompt, and the free tier allows only
    # one reply every 45 s per IP, so retry with backoff.
    body = {"model": "openai", "messages": [{"role": "user", "content": prompt}]}
    last = ""
    for i in range(tries):
        try:
            req = urllib.request.Request(
                "https://text.pollinations.ai/openai", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as fh:
                d = json.load(fh)
            text = (d["choices"][0]["message"].get("content") or "").strip()
            if text:
                return text
            last = "empty reply"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)[:120]
        time.sleep(20 * (i + 1))
    raise RuntimeError(last)


def ask_openhands(prompt: str, model: str | None = None, poll_seconds: int = 1200) -> str:
    """Delegate to a fresh OpenHands Cloud conversation and wait for its reply.

    ``model`` overrides the conversation's LLM (e.g. openhands/claude-sonnet-4-5),
    which lets one API key act as several independent advisors.
    """
    key = os.environ.get("KONGKEAT_OH_KEY") or os.environ.get("OPENHANDS_CLOUD_API_KEY") \
        or os.environ.get("OPENHANDS_API_KEY")
    if not key:
        raise RuntimeError("no OpenHands API key set")
    auth = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"initial_message": {"content": [{"type": "text", "text": prompt}]},
            "title": "ak advisor panel"}
    if model:
        body["llm_model"] = model
    start = _post(f"{OH_BASE}/api/v1/app-conversations", body, headers=auth, timeout=60)
    task_id = start.get("id")
    conv_id = start.get("app_conversation_id")
    deadline = time.time() + poll_seconds
    while not conv_id and time.time() < deadline:
        time.sleep(8)
        try:
            st = json.load(urllib.request.urlopen(urllib.request.Request(
                f"{OH_BASE}/api/v1/app-conversations/start-tasks?ids={task_id}",
                headers=auth), timeout=40))
            items = st if isinstance(st, list) else st.get("items", [])
            if items and items[0].get("app_conversation_id"):
                conv_id = items[0]["app_conversation_id"]
            if items and items[0].get("status") in ("ERROR", "FAILED"):
                raise RuntimeError(f"start task {items[0].get('status')}")
        except urllib.error.HTTPError:
            continue
    if not conv_id:
        raise RuntimeError("conversation never became ready")
    while time.time() < deadline:
        time.sleep(10)
        ev = json.load(urllib.request.urlopen(urllib.request.Request(
            f"{OH_BASE}/api/v1/conversation/{conv_id}/events/search?limit=100",
            headers=auth), timeout=40))
        items = ev if isinstance(ev, list) else ev.get("items", [])
        for e in items:
            if e.get("source") in ("assistant", "agent") and e.get("kind") == "MessageEvent":
                msg = e.get("message") or e.get("llm_message") or {}
                text = msg.get("content")
                if isinstance(text, list):
                    text = "".join(p.get("text", "") for p in text
                                   if isinstance(p, dict) and p.get("text"))
                if text and str(text).strip():
                    return str(text).strip()
    raise RuntimeError("no assistant reply before the deadline")


ADVISORS = {
    "gemini": ask_gemini,
    "pollinations": ask_pollinations,
    "openhands": ask_openhands,
    # same OpenHands key, a different underlying model -> a genuinely different advisor
    "openhands-claude": lambda p: ask_openhands(p, model="openhands/claude-sonnet-4-5"),
    "openhands-gpt": lambda p: ask_openhands(p, model="openhands/gpt-5"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--extra", default="", help="extra measured facts to include")
    ap.add_argument("--only", default="", help="comma list of advisors to use")
    ap.add_argument("--no-system", action="store_true")
    args = ap.parse_args()

    names = [n.strip() for n in args.only.split(",") if n.strip()] or list(ADVISORS)
    parts = [args.question]
    if args.extra:
        parts.insert(0, "ข้อมูลจริงที่วัดได้:\n" + args.extra)
    if not args.no_system:
        parts.append(SYSTEM)
    prompt = "\n\n".join(parts)

    # Ask every advisor at once: each OpenHands entry is a ~2-4 min conversation,
    # so running them in sequence would make the panel needlessly slow.
    results: dict[str, str] = {}

    def run(name: str) -> None:
        fn = ADVISORS.get(name)
        if fn is None:
            results[name] = "(unknown advisor)"
            return
        try:
            results[name] = fn(prompt).strip()
        except Exception as exc:  # noqa: BLE001 - a dead advisor must not stop the panel
            results[name] = f"(unavailable: {str(exc)[:200]})"

    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        list(pool.map(run, names))

    answered = 0
    for name in names:
        print(f"### {name}", flush=True)
        ans = results.get(name, "(no result)")
        if not ans.startswith("(unavailable"):
            answered += 1
        print(ans, "\n", flush=True)
    print(f"--- {answered}/{len(names)} advisors answered ---", flush=True)
    return 0 if answered else 1


if __name__ == "__main__":
    sys.exit(main())
