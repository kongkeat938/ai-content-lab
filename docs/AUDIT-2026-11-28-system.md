# AUDIT-2026-11-28 — the whole system, and the advisor layer removed

K (2026-11-28): *"ตอนนี้ ak ตรวจสอบระบบเราทั้งหมดเลยนะ พวก chat gpt หรือระบบ advisor อื่นที่
ทำงานในระบบเราตอนนี้ยกเลิกออกไปให้หมดเลยนะ ak มีอิสระที่จะทำเองทั้งหมดแล้ว"*

This is what was measured, what was deleted, and what still calls an outside model.

## 1) What the repository holds (measured 2026-11-28, `ls`/`wc`)

| thing | count | note |
|---|---|---|
| scripts (`scripts/*.py`) | 263 | before today's deletions: 273 |
| guards (`scripts/test_*.py`) | 132 | all 132 PASS locally (deps + static ffmpeg installed) |
| workflows (`.github/workflows/*.yml`) | 40 | most `disabled_manually` (see `INVENTORY-2026-11-22.md`) |
| docs (`docs/*.md`) | 151 | dated decision/panel docs are history, not instructions |

## 2) The advisor layer — deleted, not disabled

Every file below existed only to ask another model what to think. All of it is **gone**:

| file | what it did |
|---|---|
| `scripts/advise.py` | the camp registry (gemini, pollinations, kilocode, g4fspace, yqcloud) + `LIGHT`/`FAST` panels |
| `scripts/council3.py` | 3-layer council: L1 draft → L2 cross-critique → L3 decide |
| `scripts/team.py` | worker roles (researcher, scriptwriter, packager, critic, analyst, engineer) |
| `scripts/consult.py`, `scripts/consult_panel.py` | one-off "what should I change" asks |
| `scripts/panel_bench.py`, `scripts/panel_scorecard.py`, `scripts/panel_script.py` | panel scoring / script vetting |
| `scripts/writers_room.py` | several LLM writers + an LLM judge for one brief |
| `scripts/legacy/probe_advisors.py` | archived camp probe |
| guards | `test_advise_panel.py`, `test_council3.py`, `test_team.py` |

Call sites that had to change with it (they would have crashed on import):

| file | change |
|---|---|
| `scripts/writers_room.py` → `scripts/shorts_draft_gate.py` | the mechanical half survives: shape, 250–700 chars, no bare digit, no emoji, no mixed script, hook/story not a repeat. Guard `test_shorts_draft_gate.py` (15 checks). |
| `scripts/studio_ai.py` | `ask_panel()` and `--panel` removed; still writes the insights file from the measured winners |
| `scripts/video_review.py` | `ask_panel()`, `--panel`, panel rules removed; the grades/notes report stays |
| `scripts/diagnose_videos.py` | `ask_panel()`, `use_panel`, `--panel` removed; the measured burst table stays |
| `scripts/gen_short_scripts.py` | `--vet/--no-vet/--vet-rounds` (panel vetting, **on by default**) removed |
| `scripts/ak_mail.py` | roster is `["ak"]` (no worker roles) |
| `scripts/test_agent_own_email.py` | no `team` import; still fails if ak's mailbox is missing or shares a vault key |
| `scripts/test_no_repeat_paths.py` | imports `shorts_draft_gate` |

Living docs rewritten so nobody re-adds it: `AGENTS.md`, `docs/PROJECT-MAP.md`,
`docs/SYSTEM-STRUCTURE-2026-11-22.md`, `docs/AK-IDENTITY.md`, `docs/INVENTORY-2026-11-22.md`,
`.openhands/memory/MEMORY.md`.

## 3) What still calls an outside model (declared, not hidden)

Deleting the advisors does **not** mean zero external models. These generate *content*; they do
not judge our work:

| file | model | used by | verdict |
|---|---|---|---|
| `scripts/gen_knowledge_scripts.py` | Gemini text | `ch4-longform.yml` (ch4 paused) | keep — it writes the product |
| `scripts/gen_philosophy_scripts.py` | Gemini text | `genx-longform.yml` | keep — it writes the product |
| `scripts/gen_night_scripts.py`, `gen_short_scripts.py` | Gemini text | short/long script pools | keep |
| `scripts/optimize_seo.py`, `optimize_titles.py` | Gemini text | title/description drafts | keep (drafts only, ak picks) |
| `scripts/grade_video_vision.py`, `scripts/cdp_gemini_image.py` | Gemini vision/image | grading, art | keep |
| `scripts/gemini_text.py` | shared reader | all of the above | keep |

If K wants the factory to be 100% model-free, the next step is to make the procedural fallbacks
the default and delete `gemini_text.py` — that is a product decision, not a cleanup.

## 4) Verification

- Local: `for t in scripts/test_*.py` → **132 PASS / 0 FAIL** (after `pip install -r requirements.txt`
  and `static-ffmpeg`; before that, 37 fails were all `ModuleNotFoundError`).
- CI: the PR that carries this audit runs the same suite.
- No publish, no spend, no account created.
