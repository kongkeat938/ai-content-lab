# PROJECT-MAP — yt938-2 (the one map; read this before creating anything)

**Project:** `yt938-2` — run 3 Thai YouTube channels toward monetisation (YPP).
**Goal:** YPP = **1,000 subscribers + 4,000 long-form watch-hours / 12 months**.
**Steer by:** long-form watch-hours/week + `retention@2min` (Shorts do NOT count toward YPP).
**Focus:** **dharma** (96% of long-form watch time). **genx** = Shorts engine + subs.
**kongkeat-story** = PAUSED (`content/PAUSED`) — do not build for it.

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

All rails are GitHub Actions only (the pod is recycled when idle). Kill switch = `content/STOP`.

## 2) The one login path (do NOT add a second)

- **Headless (no human, the normal path):** `scripts/yt_auth.py` — refresh token in a repo
  secret. `scripts/fetch_secret.py NAME` pulls any repo secret onto the pod (encrypted transit).
- **Pod browser login (only when Studio needs it):** `scripts/pod_account_login.py`
  (`--from-secret` reads `OWNER_LOGIN_PASSWORDS`). Password is **never** typed by hand or by K.
- **Do not** add another login script. `scripts/legacy/pod_mail_login.py` was a duplicate → archived.

## 3) Where the truth lives (do not duplicate these)

- Goal + rules: `docs/GOAL.md`, `AGENTS.md` (root only), `docs/DECISION-*.md`.
- Channel facts: `channels.json`, `.openhands/memory/topics/00-*.md`.
- Measured history: `docs/STATUS-<date>.md`, `docs/counters.jsonl` (the counter), `docs/HEALTH.md`.
- The living index: `.openhands/memory/MEMORY.md` (<6,000 chars) → `topics/` → daily logs.
- **Not a place for truth:** a new file with a `b/c/d` suffix. Extend the dated file instead.

## 4) Conventions (K's rules, measured)

- **PCSEV** every problem: Problem → Cause → Solution → Execute → Verify (verify LIVE).
- Times to K: **Asia/Bangkok, 24h**. Reply in **Thai**. Decisions go to the **panel** (`advise.py`, ≥5).
- A guard must be able to FAIL; never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL.
- **Archive, don't delete** (`scripts/legacy/`): keep history, cut noise. Delete only true duplicates.
- One project, one goal. A task that does not serve YPP is out of scope — say so, don't build it.

## 5) Archived (kept for history, no live references)

`scripts/legacy/pod_mail_login.py` (superseded by `pod_account_login.py`),
`scripts/legacy/backfill_short_links.py`, `scripts/legacy/gen_branding_art.py`,
`scripts/legacy/probe_advisors.py`, `scripts/legacy/studio_drive.py`.

---
_Last audited: 2026-11-13 (ak, whole-repo pass anchored to the yt938-2 goal)._
