# 06 — The Gemini review gate (K, 2026-11-19)

K's rule, verbatim:

> "งานที่ผ่านการตรวจสอบจาก gemini เอามาให้ k ดูทั้งหมด ถ้างานไม่ได้รับการตรวจให้ผ่านจาก gemini
> และ k ห้ามอัพ"

Nothing enters `main` without a recorded Gemini APPROVE. This topic is the detail behind the
one-line rule in `MEMORY.md`.

## Why a ledger and not a promise

Before this, "was this reviewed?" was an opinion. `902d323` (playlist loop) had two rounds of
Gemini review recorded only in a daily log; `bf4c727`, `ebd489e`, `8f7dd42` and `ed20ce1` had
**no record at all** — `ed20ce1` was already pushed to `main` before anyone asked. A rule you
cannot check is a rule that is already broken.

## What exists

| Thing | Path |
|---|---|
| the ledger | `docs/reviews/ledger.json` |
| the check + CLI | `scripts/review_ledger.py` (`--status`) |
| the guard (10 FAIL paths) | `scripts/test_review_ledger.py` |
| the verdict texts | `docs/reviews/<date>-<subject>.txt` |

Two kinds of entry, never interchangeable:

* **approved** — Gemini read the file. The entry stores the `sha256` of exactly what it read
  plus the path of the verdict text. Edit one byte → **stale → re-review** (FAIL).
* **baseline** — the file predates the rule. This is **visible debt, not permission**. Edit one
  byte → the file is no longer the one that predated the rule, so it **must be reviewed** (FAIL).
  Without that second rule, any file could be quietly moved into the safe set by touching it.

Verdict parsing is deliberately strict: only the exact word `APPROVE` passes.
`APPROVE WITH CHANGES` is a real Gemini answer and it is **not** permission to ship — it means
make the change, then ask again. `REJECT` fails. A missing or unreadable evidence file is
`None`, never a pass (the same trap as the thumbnail `--skip-existing` false pass).

## The debt, measured 2026-11-19

`249 reviewable` (211 `scripts/*.py` + 38 `.github/workflows/*.yml`), **14 approved, 235 baseline**.

Gemini chose the policy (2026-11-19, `docs/reviews/2026-11-19-policy-baseline.txt`): **option C** —
baseline the old files but label them as debt and keep the number visible, rather than exempting
everything (a false pass) or blocking all work until 247 files are reviewed (no quality in a rush).
Its ordering advice, when the debt is worked down:

1. anything touching credentials / the YouTube API / auto-upload (a strike risk),
2. the high-frequency rails,
3. the 38 workflows,
4. utilities.

Batch 10–15 files a day; the count is printed by `review_ledger.py --status` on every CI run.

## How to review a change (the only correct order)

1. Make the change. Run the suite.
2. Send Gemini the **real diff or the whole file** plus the measured context it needs.
3. Save its reply to `docs/reviews/<date>-<subject>.txt` — do not paraphrase, do not edit it.
4. Add/refresh the `approved` entry with the file's current `sha256` and that evidence path.
5. `python3 scripts/review_ledger.py` → must be rc=0 before commit.

**Never edit an evidence file to make it read APPROVE.** If Gemini said `APPROVE WITH CHANGES`,
make the change and ask again — that is what happened with the `::group::` request on
`selftest.yml` (round 1 = APPROVE WITH CHANGES, round 2 = APPROVE).

## Honest limits

* A digest proves the evidence is about *this content*. It does not prove a human read it.
  Fabricating a verdict file is possible; it is also visible in the diff, which is why the
  evidence file carries Gemini's own words and the ledger stores the digest beside it.
* The guard covers `scripts/*.py` and `.github/workflows/*.yml`. Content JSON and docs are out of
  scope — they are data, not behaviour.
* ak writes the code and asks for the review. Gemini's 2026-11-19 answer to "how do we stop ak
  approving its own work" was: the ledger must record the evidence, not ak's word, and a change
  without evidence must fail. That is what this is.
