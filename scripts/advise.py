#!/usr/bin/env python3
"""Ask the advisor panel one question and print the answer.

K's rule (changed 2026-11-18): the advisor panel is **Gemini alone** -- one
vendor, one model family. *"ทีมที่ปรึกษาให้ใช้ gemini คนเดียวพอ"*. And when a
problem comes up, ak **follows Gemini's instruction**: *"ต้องทำตามคำสั่งและแนะนำ
ของ gemini เมื่อติดปัญหา"*. So a single Gemini call is the whole panel, and its
advice is binding when ak is stuck -- not one voice among five.

This replaces the earlier five-voice / two-vendor rule. The five Gemini models
and pollinations were all the *same* question asked several ways; the measured
failure mode was a dead vendor stalling a decision (openrouter had no key, every
call raised). One vendor that answers is more useful than five that may not.
Measured live 2026-11-18: `ask_gemini` answers ("2+2" -> "4") and the key lists
50 models, so Gemini text is up.

`pollinations` and the OpenHands advisors stay in the registry for an explicit
`--only` call, but they are **not** in any default panel. `--deep` is opt-in.

    python3 scripts/advise.py "what should I change first?"
    python3 scripts/advise.py --extra "28-day: Shorts 30.3h, long-form 2.9h" "..."
    python3 scripts/advise.py --only pollinations "compare with another vendor"
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


def ask_gemini(prompt: str, models: tuple[str, ...] = GEMINI_MODELS,
               tries: int = 3) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    last = ""
    for model in models:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
               f":generateContent?key={key}")
        for attempt in range(tries):
            try:
                d = _post(url, {"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"temperature": 0.7}})
                return d["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as exc:
                last = f"{model}: HTTP {exc.code}"
                # 503 = the shared key is momentarily saturated (four panel
                # entries call it at once); back off and retry.
                if exc.code in (429, 500, 503):
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            except Exception as exc:  # noqa: BLE001 - try the next model
                last = f"{model}: {exc}"
                time.sleep(2 * (attempt + 1))
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
    # A short alias the light panel asks for. Measured 2026-11-11: four scripts
    # (studio_ai, video_review, diagnose_videos, panel_scorecard) asked for
    # "gemini" -- which was not a key here -- and every one of them skipped it
    # silently, so the "panel" ran on pollinations alone (or on nothing when
    # pollinations 400'd). Keep the alias so a plain name always resolves.
    "gemini": lambda p: ask_gemini(p, ("gemini-3.5-flash-lite",)),
    # fast, free, seconds -- the default team
    "gemini-3.5": lambda p: ask_gemini(p, ("gemini-3.5-flash-lite",)),
    "gemini-3.1": lambda p: ask_gemini(p, ("gemini-3.1-flash-lite",)),
    "gemini-flash": lambda p: ask_gemini(p, ("gemini-3.5-flash",)),
    "gemini-preview": lambda p: ask_gemini(p, ("gemini-3-flash-preview",)),
    # a genuinely different vendor that needs no key; slower than Gemini
    # (measured 0.3-42 s) but the panel runs in parallel.
    "pollinations": ask_pollinations,
    # slow but genuinely different vendors -- opt in with --deep
    "openhands": ask_openhands,
    "openhands-claude": lambda p: ask_openhands(p, model="openhands/claude-sonnet-4-5"),
    "openhands-gpt": lambda p: ask_openhands(p, model="openhands/gpt-5"),
}

# The default team: **Gemini alone** (K, 2026-11-18). One vendor, one call. The
# `ask_gemini` chain still falls through several Gemini models, so a busy model
# does not stop the answer -- but the panel is one vendor, by K's rule.
FAST = ["gemini"]
FAST_PLUS = FAST
BROAD = FAST
# Opt-in only (not in any default panel): another vendor / the slow Cloud advisors.
DEEP = ["openhands", "openhands-claude", "openhands-gpt"]


def resolve_team(names: list[str]) -> list[str]:
    """De-duplicate a panel so a name is never counted twice."""
    out: list[str] = []
    for name in names:
        if name not in out:
            out.append(name)
    return out

# The small panel the learning loop and the graders ask. K's rule (2026-11-18):
# Gemini alone. The old two-vendor LIGHT pair ("gemini" + "pollinations") is gone;
# a decision is Gemini's, and ak follows it. Defined here, next to the registry, so
# a script cannot name an advisor that does not exist (the bug that silently
# emptied this panel, 2026-11-11).
LIGHT = ["gemini"]


def advisor(name: str):
    """The callable for `name`, or a loud error if the name is not registered.

    A name missing from the registry is a wiring bug, not a dead vendor, so it
    must fail here rather than be skipped: `.get(name)` + `continue` is exactly
    how the light panel quietly lost its Google advisor for days.
    """
    fn = ADVISORS.get(name)
    if fn is None:
        raise KeyError(f"unknown advisor {name!r}; known: {sorted(ADVISORS)}")
    return fn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--extra", default="", help="extra measured facts to include")
    ap.add_argument("--only", default="", help="comma list of advisors to use")
    ap.add_argument("--broad", action="store_true",
                    help="deprecated no-op: the default panel is Gemini alone (K, 2026-11-18)")
    ap.add_argument("--deep", action="store_true",
                    help="also ask the slow OpenHands advisors (2-20 min each)")
    ap.add_argument("--no-system", action="store_true")
    args = ap.parse_args()

    if args.only:
        names = [n.strip() for n in args.only.split(",") if n.strip()]
    else:
        names = resolve_team((BROAD if args.broad else FAST) + (DEEP if args.deep else []))
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
