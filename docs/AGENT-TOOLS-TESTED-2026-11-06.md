# Which coding-agent tools actually help — tested from the pod (2026-11-06)

K: "ตัวไหนช่วยงานจริงได้ เอามาลอง ถ้าช่วยงานไม่ได้ไม่ต้อง." Every verdict below is
from a **real run in this pod**, not a feature list.

## Aider — ✅ เก็บไว้ใช้

- Installed with `uv tool install aider-chat --with audioop-lts`. Python 3.13
  dropped `audioop`, which aider's `pydub` import needs; the `--with audioop-lts`
  shim is what makes it start. Binary: `~/.local/bin/aider` (put it on `PATH`).
- Proved with **two free routes**, both on real tasks:
  - **Pollinations (keyless):** `OPENAI_API_BASE=https://text.pollinations.ai/openai`,
    `OPENAI_API_KEY=dummy`, `--model openai/openai-fast`. Fixed a `-`/`+` bug in
    `calc.py` **and** wrote `test_calc.py` — passed.
  - **Google free key:** `OPENAI_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai`,
    `OPENAI_API_KEY=$GEMINI_API_KEY`, `--model openai/gemini-3.5-flash-lite`.
    Wrote a Thai number-speller (`0→ศูนย์ … 1234→หนึ่งพันสองร้อยสามสิบสี่`); every
    case passed, no hard-coding.
- **Why it helps here:** it is a second, independent coding camp that runs on the
  free keys we already hold, edits files in the repo directly, and works with git.
  Best for isolated, well-specified chores — a helper script, a test, a small
  refactor. Not for the YouTube rail.
- Cosmetic wart: at exit it prints `Summarization failed … cannot schedule new
  futures after shutdown`; harmless, the edits are already applied.

## Devika — ❌ ไม่คุ้ม (measured)

- Repo alive (last commit 2025-09), but installs heavy: `torch`, `keybert`,
  `playwright`, `eventlet`.
- Boot fails on stale deps: `ImportError: cannot import name 'Mistral' from
  'mistralai'` — the library's API moved on. Patching one layer only exposes the
  next; it needs chasing a moving target.
- Needs its own web UI, a browser session and a search-engine key.
- Verdict: the effort buys a worse coding agent than the one already running. Skip.

## Devin / Replit Agent — not applicable

Paid, and they run on the vendor's cloud. Nothing to install or measure here. Skip.

## Docker

Available (`docker 29.9.2`). Start with `sudo dockerd > /tmp/dockerd.log 2>&1 &`;
the socket needs `sudo`. Useful if we later want a containerised tool, not needed
for aider.
