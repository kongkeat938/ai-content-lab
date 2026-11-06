#!/usr/bin/env python3
"""Ask a panel of independent AI advisors the same brief, and collect their answers.

K's standing order is to consult five advisors before committing to a plan, so the
advice is not one model's opinion. The panel mixes vendors (Google) and model
families (Gemini, Gemma, GPT-OSS) so the answers are less correlated than five
prompts to one model.

Reachable from the pod (measured 2026-11-05; the sandbox egress proxy stubs
models.github.ai and every keyed vendor host, so only these two routes answer):

  * Google Generative Language API  (GEMINI_API_KEY)
  * Pollinations text API           (no key)

    python3 scripts/consult_panel.py --brief docs/CONSULT-2026-11-05b.md \
        --out docs/PANEL-2026-11-05b.md

Every advisor sees the same brief and is asked to answer in Thai. Answers are
printed as they arrive and written to one file for side-by-side comparison.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
POLLINATIONS = "https://text.pollinations.ai/openai"
LLM7 = "https://api.llm7.io/v1/chat/completions"

# (vendor, model label, model id, transport)
PANEL = [
    ("Google",     "gemini-3.5-flash-lite", "gemini-3.5-flash-lite", "gemini"),
    ("Google",     "gemini-3.6-flash",      "gemini-3.6-flash",      "gemini"),
    ("Google",     "gemma-4-31b-it",        "gemma-4-31b-it",        "gemini"),
    ("OpenAI-OSS", "gpt-oss-20b",           "openai-fast",           "pollinations"),
    ("DeepSeek",   "deepseek-v4-flash",     "DeepSeek-V4-Flash-0731", "llm7"),
]

SYSTEM = ("You are a YouTube growth and monetisation consultant for a Thai content "
          "operation. Answer in Thai, concisely, ordered by return-on-effort, and cite "
          "the numbers in the brief. State plainly what NOT to do and why. No generic advice.")


def _post(url: str, body: dict, headers: dict, timeout: int = 240) -> str:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read().decode()


def ask_gemini(model: str, prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return "(no GEMINI_API_KEY)"
    body = {"contents": [{"parts": [{"text": SYSTEM + "\n\n" + prompt}]}],
            "generationConfig": {"temperature": 0.6}}
    try:
        data = json.loads(_post(GEMINI.format(model=model) + f"?key={key}", body, {}))
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as exc:
        return f"(HTTP {exc.code}: {exc.read().decode()[:200]})"
    except Exception as exc:  # noqa: BLE001
        return f"({type(exc).__name__}: {exc})"


def ask_pollinations(model: str, prompt: str) -> str:
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": prompt}]}
    try:
        data = json.loads(_post(POLLINATIONS, body, {}))
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        return f"(HTTP {exc.code}: {exc.read().decode()[:200]})"
    except Exception as exc:  # noqa: BLE001
        return f"({type(exc).__name__}: {exc})"


def ask_llm7(model: str, prompt: str) -> str:
    """llm7.io is an anonymous OpenAI-compatible relay; DeepSeek-V4-Flash is free."""
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": prompt}],
            "max_tokens": 2048}
    try:
        data = json.loads(_post(LLM7, body, {}))
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        return f"(HTTP {exc.code}: {exc.read().decode()[:200]})"
    except Exception as exc:  # noqa: BLE001
        return f"({type(exc).__name__}: {exc})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--brief", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    prompt = (open(os.path.join(ROOT, args.brief), encoding="utf-8").read()
              if args.brief else args.question)
    if not prompt:
        sys.exit("give a question or --brief")

    results = []
    for vendor, label, model, kind in PANEL:
        print(f"\n{'='*72}\n### {vendor} — {label}\n{'='*72}", flush=True)
        if kind == "gemini":
            ans = ask_gemini(model, prompt)
        elif kind == "llm7":
            ans = ask_llm7(model, prompt)
        else:
            ans = ask_pollinations(model, prompt)
        print(ans, flush=True)
        results.append((vendor, label, ans))

    if args.out:
        with open(os.path.join(ROOT, args.out), "w", encoding="utf-8") as fh:
            fh.write(f"# Advisor panel — {len(results)} advisors\n\n")
            for vendor, label, ans in results:
                fh.write(f"## {vendor} — {label}\n\n{ans}\n\n---\n\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
