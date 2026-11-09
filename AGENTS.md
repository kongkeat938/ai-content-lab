# AGENTS.md — instructions for any agent working in this repository

Owner **K** (Thai) wants **measured evidence, not claims**. Answer in Thai. Agent name `ak`.

## PCSEV is mandatory (K, 2026-11-08)
Every problem K is shown MUST be framed as five steps:

1. **Problem** — what is wrong, concretely.
2. **Cause** — the root cause, *measured*, not guessed.
3. **Solution** — the fix.
4. **Execute** — the change, done (not proposed).
5. **Verify** — proof it worked, **measured live at the time**.

**Verify rule (the step K checks):** never verify against our own committed docs — a doc is
just another claim, and it goes stale. Trust order:

> **live API / live action > real output file (ffprobe, ebur128) > a test that can FAIL >
> committed doc (weakest).**

A doc tells you *where* to measure, not *what the answer is*. The best verify is a **counter
with an invariant** (lifetime views/subs must not fall, must not sit still) — it carries the
truth in itself. See `docs/PCSEV-VERIFY-2026-11-08.md`, `scripts/verify_claims.py`,
`scripts/counter_ledger.py`.

If a step cannot be completed yet (e.g. it needs a human at a machine), **say so plainly** —
an incomplete PCSEV stated honestly beats a finished-looking claim.

## Durable rules
- **A guard must be able to FAIL.** A test that only checks the happy path proves nothing.
- **An LLM is not a primary source.** Read the vendor's own rule, or measure live.
- **Never hardcode** the set a "threshold vs cadence" guard checks — sweep the source
  (this is why the false-alarm bug survived in `link-shorts`/`set-thumbnails`).
- **A generator that can drop a piece must FAIL**, not write a partial set.

## Pod environment
Recycled often: reinstall `ffmpeg` + `pip install -r requirements.txt` each session; re-export
`GH_TOKEN` (`KONGKEAT_GH_TOKEN`). Full suite: `for t in scripts/test_*.py; do python3 "$t"; done`.
