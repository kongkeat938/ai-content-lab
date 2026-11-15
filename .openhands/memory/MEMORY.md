# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. **This file is a MAP** (injected each session, tail truncated): keep
<6,000 chars (`test_memory_budget.py`); detail in `topics/`/logs/`docs/`. **Project = `yt938-2`;
read `docs/PROJECT-MAP.md` first; never a second copy (K; `test_project_map.py`).**

## 🪪 ak's identity & team (K, 2026-11-13; every agent its OWN mail 2026-11-14)
**Every tool/agent uses its OWN mailbox, never K's** (K, 2026-11-14). ak = `ak_mail.py`
(key `ak.identity.mailbox`); each worker = `ak.identity.mail.<role>` (`ak_mail.py` /
`team.py mail <role>`). K's channel addresses are **business assets** (YouTube API), not
signup emails; never sign up as K (`test_agent_own_email.py`). **Workers** (`team.py run
<role>`) DO the work; panel advises.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts don't count); steer by long-form watch-hours/week +
  `retention@2min`, never raw views. **dharma = 96% of long-form watch time → concentrate there.**
- **The first 2 minutes binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** on the hook.
- **Longer is better per view** (120-min ≈ **6.0** vs 17-min ≈ 4.6 min/view). **`content/PAUSED`**
  pauses a channel's rails. **Cadence: step up, don't jump** (dharma 1→2/week; each video must
  differ or it risks "repetitious content").

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order: **live
  API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**. Best =
  a **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai (UTC+7) `HH:MM`**. `PROGRESS.md`'s ONLY source is `watch_hours.json`
  (weekly rail) — if it lapses the headline freezes.
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on a spent quota → use **per-channel
  secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel
  `advise.py` (≥5). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set it sweeps; a generator that can drop
  a piece must FAIL. `.get()+continue` on a config key is a silent killer
  (`test_no_pinned_recent_date.py`).
- **Repo hygiene** (`test_repo_hygiene.py`): pushing rails `git pull --rebase`+retry; a
  shared-ledger writer needs a guard; health thresholds > the REAL cadence.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS, not an attacker** (measured 2026-11-15; K was right): the alert's
  `en-US`/category-27 signature was **never measured** (audit reads only
  snippet/statistics/contentDetails) and is false -- the clips carry `th`/cat 22-24 + our own
  `— ช่องพี่น้อง —` promo. `fn38n2-CRm0` is entry 88 of `content/ch1_shorts.json`. The sibling
  repo `aeris-drive-automation` maps ch1/ch2/ch4 and holds the SAME `YT_CH*_REFRESH_TOKEN`
  secrets -> a shared-identity bug. Fix = per-repo OAuth client + revoke; guard
  `test_rogue_alert_body.py`. `rogue_watch_rss.py` (RSS, no quota) also runs in `watchdog`.
  - **`videos.update` REPLACES the whole `snippet`** — read-merge-write
    (`test_snippet_update_preserves.py`).
- **Repo is PUBLIC** (free plan → private would halt the rails): never commit a credential
  (`test_no_committed_secrets.py`) or a real address (`test_no_committed_pii.py`); K's were
  scrubbed from tree AND history, real ones in the `CH_ACCOUNTS` secret. **Mail rail leaked them back** (echoed the raw IMAP user into
    `docs/MAIL-ALERTS.md`); labels now use `public_address()` (`test_mail_credentials.py`).
- **Quota:** `videos.insert` own pool; a GITHUB_TOKEN push does NOT trigger a workflow
- **Git/CI hygiene:** racing rails → one concurrency group per channel + a union merge driver
  (`git_push_retry.sh`); a GENERATED `docs/` report needs ONE writer rail (`test_report_single_writer.py`; `test_push_retry_union.py`).
- **One duration parser:** `scripts/yt_duration.py` (never raises; `P0D`/`P1DT2H`); the old copy-pasted regex crashed a rail (`test_duration_parse.py`).
- **Long-form rails:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; a long
  hook kills retention (cap 220); never downgrade a LIVE entry. **Content dir per-RUN
  (`%G%V_r${GITHUB_RUN_NUMBER}`) on EVERY `%G%V` rail + theme ROTATES** — else a raised
  cadence is a no-op or an add/add conflict.
- **TTS fallback:** the alt Thai voice (`PremwadeeNeural`) refuses some texts
  (`NoAudioReceived`) → `speak()` falls back to VOICE (`test_tts_fallback.py`).
- **Every new mechanism seeds a false alarm until the sweep learns it** (pre-08:00-UTC 403
  = spent quota, not an outage).
- **Pausing a channel drops it from each rail's `matrix`; unpausing must PUT IT BACK**
  (`test_rail_channels.py`). **Audit blind to a take-down** (→ `find_removed`).
  **Mail=cloud, not PC1** (dead).
- **ch4 UNPAUSED 2026-11-13**: a tension hook is **enforced** (`test_hook_concrete`) for the
  long-form hook AND the Shorts pool; no "full clip" CTA (`test_ch4_cta`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md` · daily logs.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`, `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account — genx `ch1`, dharma `ch2`, ch4
  `ch4` (`test_channel_accounts.py`).
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 BLOCKED
  (`uploadLimitExceeded` API-only; web Studio works). Needs K's OWNER password.
- **Pod env:** recycled → reinstall `ffmpeg` + `pip -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`; suite = every `scripts/test_*.py` (70).
- **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`).
