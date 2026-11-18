# PROJECT-MAP — yt938-2 (the one map; read this before creating anything)

**Project:** `yt938-2` — run 3 Thai YouTube channels toward monetisation (YPP).
**Goal:** YPP = **1,000 subscribers + 4,000 long-form watch-hours / 12 months**.
**Steer by:** long-form watch-hours/week + `retention@2min` (Shorts do NOT count toward YPP).
**Focus:** **dharma** (96% of long-form watch time). **genx** = Shorts engine + subs.
**kongkeat-story** = ch4, **LIVE** (name **"PCSEV"**, @PCSEV). Paused 2026-11-12, **UNPAUSED
2026-11-13** on K's order — `content/PAUSED` has no active line.

> Rule (K, 2026-11-13): **search this map first. If a thing already exists, use it —
> do not create a second one under a new name.** New file? add it here in the same commit.

---

## 1) The rails that matter (34 workflows; the ones driving the goal)

| Workflow | When (UTC) | Does | Goal link |
|---|---|---|---|
| `foreman.yml` | `*/30` | dispatches every due rail | the driver |
| `watchdog.yml` | `45 */4` | self-chaining keeper | keeps rails alive |
| `publish-batch.yml` | `17 */3` | uploads ready long-form | the long-form pipeline |
| `night-compilation.yml` | Mon 02:17 | builds 120-min dharma compilations | **watch-hours engine** |
| `publish-shorts.yml` | 01/09/17:30 | uploads Shorts | reach + subs |
| `studio-ai.yml` | 21:45 | Analytics → panel → insights | the learning loop |
| `counter-ledger.yml` | 04:43 | invariant counter | **the proof meter** |
| `account-watch.yml` | 08:42 | delegated-credential probe | guard (delegate publish) |
| `rogue-guard.yml` | `*/30` | hides live rogue uploads | containment |
| `progress.yml` / `watch-hours.yml` | 07:12 / Mon 06:17 | YPP progress | the scoreboard |
| `channel-branding.yml` / `ch2-playlists.yml` / `set-thumbnails.yml` | after 08:00 | packaging | search + conversion |
| `link-shorts.yml` | driven by the foreman | appends the long-form playlist link to every Short's description (the reach → watch-hours funnel) | **the funnel** |
| `make_motion_short.py` (a tool, not a rail) | by hand | an animated still Short whose layers match the story's `genre` -- dharma/genx = calm (twinkle + petals, no mascot, no glow disc), knowledge = a mascot dancing to the beat | a livelier Shorts shape (reach) that still fits the story |
| `make_ambient_video.py` (a tool, not a rail) | by hand | stitches real b-roll (`fetch_broll.py`, Coverr) into one long 1080x1920 ambient video, looped to `--minutes`, bed at -14 LUFS | the "join clips + 3-min music" edit K wanted, done headless |

All rails are GitHub Actions only (the pod is recycled when idle). Kill switch = `content/STOP`.

## 2) The one login path (do NOT add a second)

- **Headless (no human, the normal path):** `scripts/yt_auth.py` — refresh token in a repo
  secret. `scripts/fetch_secret.py NAME` pulls any repo secret onto the pod (encrypted transit).
- **Pod browser login (only when Studio needs it):** `scripts/pod_account_login.py`
  (`--from-secret` reads `OWNER_LOGIN_PASSWORDS`). Password is **never** typed by hand or by K.
- **Do not** add another login script. `scripts/legacy/pod_mail_login.py` was a duplicate → archived.

## 3) Where the truth lives (do not duplicate these)

- Goal + rules: `docs/GOAL.md`, `AGENTS.md` (root only), `docs/DECISION-*.md`.
- Goal consults / panels: `docs/CONSULT-*.md` (the brief + the answer, incl. the measured numbers)
  and `docs/PANEL-*.md`. `docs/GROWTH-PLAN-*.md` is the plan that follows a consult. The latest
  goal consult is `docs/CONSULT-2026-11-18-goal.md` (Gemini alone) — it also records where
  Gemini's advice **conflicts with the measured data** (genx subs).
- Channel facts: `channels.json`, `.openhands/memory/topics/00-*.md`.
- Channel NAMES: a channel's main title is **not API-settable** — K sets it in Studio, so the
  repo *follows* the live name (verified quota-free from RSS / channel page / oEmbed). Single
  writer `scripts/set_channel_name.py` (`TARGET`); ch4 = **PCSEV** (@PCSEV). The bare genre word
  ("เกร็ดความรู้รอบตัว") stays in keywords/SEO — only the channel-name labels/phrases are PCSEV.
  Guard `scripts/test_ch4_channel_name.py` (fails if a rail would write the retired name back).
- Measured history: `docs/STATUS-<date>.md`, `docs/counters.jsonl` (the counter), `docs/HEALTH.md`.
- The living index: `.openhands/memory/MEMORY.md` (<6,000 chars) → `topics/` → daily logs.
- **ak's own identity:** `docs/AK-IDENTITY.md` + `scripts/ak_mail.py` (ak's mailbox, KV vault).
- **ak's team of workers:** `scripts/team.py` (`list|run|all`); roles = researcher, scriptwriter,
  packager, critic, analyst (fast) + engineer (Cloud). Advisors registry: `scripts/advise.py`.
- **Quality = Gemini (free):** the panel is Gemini alone (K, 2026-11-18). A build that FAILS a gate
  is handed to Gemini for a fix (`scripts/fix_with_gemini.py`, wired into `qa_gate` veto and
  `short_standard` hold; it never clears the gate). Free stack + limits: `docs/QUALITY-FREE-2026-11-18.md`.
- **One reader for a Gemini reply:** `scripts/gemini_text.text_of` joins EVERY `content.parts`
  entry — a reply can arrive split in two, and `parts[0]` alone cuts mid-word while the API still
  says `finishReason: STOP` (measured 2026-11-18; guard `scripts/test_gemini_text.py` sweeps the
  source). Every `ask_gemini`-style call site imports it.
- **Vision quality check (manual, NEVER gates CI):** `scripts/grade_video_vision.py` samples N
  frames across a finished file and asks Gemini for a 0-10 rubric score. It is non-deterministic
  (measured 2026-11-17: the same cut scored 9 then 5/10), so a human/agent reads it — no workflow
  calls it (guard `scripts/test_vision_grader.py` fails if a rail wires it in).
- **Not a place for truth:** a new file with a `b/c/d` suffix. Extend the dated file instead.

## 4) Conventions (K's rules, measured)

- **PCSEV** every problem: Problem → Cause → Solution → Execute → Verify (verify LIVE).
- Times to K: **Asia/Bangkok, 24h**. Reply in **Thai**. Decisions go to the **panel** (`advise.py`;
  **Gemini alone**, K 2026-11-18 -- follow its advice when stuck).
- A guard must be able to FAIL; never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL.
- **A rail that cannot do its job must not report success** (measured 2026-11-18: the shared
  Data-API pool was spent every day, `link-shorts` ran the funnel as `... || true` and went
  GREEN while the funnel stayed unwired; `set-thumbnails --check` called an unreadable API
  "auto/other" and showed 12 live covers as unset). A spent quota is a **deferral (exit 2)**,
  an unreadable state is **unknown, not "not ours"**. Guard `scripts/test_no_silent_funnel.py`.
- **Archive, don't delete** (`scripts/legacy/`): keep history, cut noise. Delete only true duplicates.
- **Shorts quality is gated before upload** (`scripts/publish_shorts.py`): aspect/colour/thumbnail
  (`short_standard.py`, `test_short_standard.py`) and loudness (measured, not a fixed gain —
  `test_short_loudness.py`). A build that misses the standard is HELD, not uploaded.
- One project, one goal. A task that does not serve YPP is out of scope — say so, don't build it.

## 5) Archived (kept for history, no live references)

`scripts/legacy/pod_mail_login.py` (superseded by `pod_account_login.py`),
`scripts/legacy/backfill_short_links.py`, `scripts/legacy/gen_branding_art.py`,
`scripts/legacy/probe_advisors.py`, `scripts/legacy/studio_drive.py`.

---
_Last audited: 2026-11-18 (ak, whole-repo pass anchored to the yt938-2 goal)._
