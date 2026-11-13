#!/usr/bin/env python3
"""Probe which free advisor routes actually answer from this pod.

K's rule: measure, do not trust reputation. This script makes real calls and
prints what came back, so a route is only "usable" if it returned a completion.

    python3 scripts/probe_advisors.py

llm7 is probed one request at a time on purpose: it throttles concurrency, and a
parallel sweep makes every model look dead with "Too many concurrent requests".
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
PROMPT = "Reply with the single word: OK"


def _post(url: str, body: dict, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST", headers={**UA, **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read().decode(errors="replace")


def probe(name: str, url: str, body: dict, headers: dict | None = None) -> bool:
    try:
        out = _post(url, body, headers)
        text = out[:120].replace("\n", " ")
        print(f"  OK    {name:22s} {text}")
        return True
    except urllib.error.HTTPError as e:
        print(f"  {e.code:<5} {name:22s} {e.read().decode(errors='replace')[:90]}")
    except Exception as e:  # noqa: BLE001 - report and continue
        print(f"  ERR   {name:22s} {type(e).__name__}: {str(e)[:70]}")
    return False


def main() -> int:
    ok = []
    chat = lambda m: {"model": m, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 20}

    print("Google (GEMINI_API_KEY):")
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("  SKIP  GEMINI_API_KEY not set")
    for m in ("gemini-3.5-flash-lite", "gemma-4-31b-it"):
        if key and probe(
            m,
            f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}",
            {"contents": [{"parts": [{"text": PROMPT}]}]},
        ):
            ok.append("google/" + m)

    print("OpenAI-OSS (Pollinations, keyless):")
    if probe("openai-fast", "https://text.pollinations.ai/openai", chat("openai-fast")):
        ok.append("pollinations/openai-fast")

    print("Zhipu / DeepSeek (llm7, keyless, sequential):")
    for m in ("GLM-5.3-Flash", "DeepSeek-V4-Flash-0731"):
        if probe(m, "https://api.llm7.io/v1/chat/completions", chat(m)):
            ok.append("llm7/" + m)
        time.sleep(5)

    print("Image (Pollinations, keyless):")
    try:
        req = urllib.request.Request(
            "https://image.pollinations.ai/prompt/a%20thai%20temple?width=512&height=512&nologo=true",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=90) as fh:
            blob = fh.read()
        print(f"  OK    image.pollinations   {fh.status} {fh.headers.get('Content-Type')} {len(blob)} bytes")
        ok.append("pollinations/image")
    except Exception as e:  # noqa: BLE001
        print(f"  ERR   image.pollinations   {type(e).__name__}: {str(e)[:70]}")

    print("\nUSABLE NOW:", ", ".join(ok) if ok else "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
