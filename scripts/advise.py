#!/usr/bin/env python3
"""Ask a panel of independent AI advisors one question and print every answer.

K's rule: never bring a decision to a person; take it to an AI. K also requires
**at least five advisors on every question** -- a single vendor is a single point
of failure, and one dead vendor must never stop a decision. This asks the whole
panel and reports which answered.

Default panel (fast, seconds): five advisors drawn from the two free providers
that answer from the pod (measured 2026-11-09; every other keyless vendor is
refused by the pod's egress proxy):

  1. gemini-3.5-flash-lite  -- GEMINI_API_KEY, one independent model
  2. gemini-3.1-flash-lite  -- same key, a second model
  3. gemini-flash-lite-latest
  4. gemini-3-flash-preview -- same key, a fourth model
  5. pollinations           -- text.pollinations.ai, no key, a different vendor

The Gemini entries share a key but run different models, so the panel is five
independent opinions, not five copies of one.

The default panel adds a sixth advisor, **openrouter** (OpenRouter free tier,
key in OPENROUTER_API_KEY or ~/.pod-openrouter-key), which fronts yet other
vendors (Nvidia, Cohere). It is on by default because it is a genuinely
different vendor; use ``--fast`` to drop it when the shared free pool is busy.

**Deep mode** (`--deep`) adds three OpenHands Cloud conversations (its own
DeepSeek agent, Claude Sonnet, GPT-5) on KONGKEAT_OH_KEY. They are genuinely
independent vendors but each takes 2-20 minutes, so they are opt-in only.

    python3 scripts/advise.py "what should I change first?"
    python3 scripts/advise.py --deep "the slow, high-stakes question"
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
# Free OpenRouter models, each a different vendor (Nvidia / Cohere). The shared
# free pool is rate-limited, so they are tried in order as extra panelists.
OPENROUTER_MODELS = ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                     "cohere/north-mini-code:free",
                     "nvidia/nemotron-3.5-lightning:free")
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


def ask_openrouter(prompt: str, models: tuple[str, ...] | None = None,
                   tries: int = 3) -> str:
    """Ask OpenRouter with a free-tier key (openrouter.ai).

    OpenRouter fronts many independent vendors (Nvidia, Cohere, Google, ...),
    so a single key yields genuinely different opinions -- but the free pool is
    shared and rate-limited upstream, so try several models and back off.
    """
    key = (os.environ.get("OPENROUTER_API_KEY") or _read_key_file()).strip()
    if not key:
        raise RuntimeError("no OpenRouter key (OPENROUTER_API_KEY or ~/.pod-openrouter-key)")
    models = models or OPENROUTER_MODELS
    last = ""
    for model in models:
        for attempt in range(tries):
            try:
                d = _post("https://openrouter.ai/api/v1/chat/completions",
                          {"model": model,
                           "messages": [{"role": "user", "content": prompt}],
                           "max_tokens": 1200},
                          headers={"Content-Type": "application/json",
                                   "Authorization": f"Bearer {key}"},
                          timeout=180)
                text = (d["choices"][0]["message"].get("content") or "").strip()
                if text:
                    return text
                last = f"{model}: empty reply"
            except urllib.error.HTTPError as exc:
                last = f"{model}: HTTP {exc.code}"
                if exc.code in (429, 500, 502, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            except Exception as exc:  # noqa: BLE001 - try the next model
                last = f"{model}: {str(exc)[:100]}"
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(last)


def _read_key_file() -> str:
    path = os.path.expanduser("~/.pod-openrouter-key")
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return ""


ADVISORS = {
    # fast, free, seconds -- the default panel
    "gemini-3.5": lambda p: ask_gemini(p, ("gemini-3.5-flash-lite",)),
    "gemini-3.1": lambda p: ask_gemini(p, ("gemini-3.1-flash-lite",)),
    "gemini-flash": lambda p: ask_gemini(p, ("gemini-3.5-flash",)),
    "gemini-preview": lambda p: ask_gemini(p, ("gemini-3-flash-preview",)),
    "pollinations": ask_pollinations,
    # a genuinely different vendor (OpenRouter fronts Nvidia/Cohere); opt in
    # because the shared free pool is often rate-limited.
    "openrouter": ask_openrouter,
    # slow but genuinely different vendors -- opt in with --deep
    "openhands": ask_openhands,
    "openhands-claude": lambda p: ask_openhands(p, model="openhands/claude-sonnet-4-5"),
    "openhands-gpt": lambda p: ask_openhands(p, model="openhands/gpt-5"),
}

FAST = ["gemini-3.5", "gemini-3.1", "gemini-flash", "gemini-preview", "pollinations"]
FAST_PLUS = FAST + ["openrouter"]
DEEP = ["openhands", "openhands-claude", "openhands-gpt"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--extra", default="", help="extra measured facts to include")
    ap.add_argument("--only", default="", help="comma list of advisors to use")
    ap.add_argument("--fast", action="store_true",
                    help="five Gemini/Pollinations advisors only (skip OpenRouter)")
    ap.add_argument("--deep", action="store_true",
                    help="also ask the slow OpenHands advisors (2-20 min each)")
    ap.add_argument("--no-system", action="store_true")
    args = ap.parse_args()

    if args.only:
        names = [n.strip() for n in args.only.split(",") if n.strip()]
    else:
        names = (FAST if args.fast else FAST_PLUS) + (DEEP if args.deep else [])
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
