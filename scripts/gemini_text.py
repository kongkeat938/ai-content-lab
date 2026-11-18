#!/usr/bin/env python3
"""One way to read a Gemini reply's text -- join EVERY part, never just the first.

Measured 2026-11-18: a live `generateContent` reply came back with `nparts=2`
(`content.parts = [{text: "...mid-wo"}, {text: "rd..."}]`) and a reader that takes
`parts[0]["text"]` alone returns a string cut mid-word. The API still reports
`finishReason: STOP` and a plausible `candidatesTokenCount`, so the truncation is
silent -- it looks exactly like a short answer. Nine call sites had this shape
(advise, gen_*_scripts, optimize_*, consult*, panel_script).

`text_of(data)` is the one place that knows how to read a Gemini response, so a
generator that splits its answer can never drop the tail again.

    from gemini_text import text_of
    return text_of(json.load(fh))
"""
from __future__ import annotations


def text_of(data: dict) -> str:
    """All text of the first candidate, every part joined, stripped."""
    candidates = (data or {}).get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", []) or []
    return "".join(p.get("text", "") for p in parts).strip()
