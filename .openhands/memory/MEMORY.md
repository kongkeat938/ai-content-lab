# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. **This file is a MAP** (injected each session, tail truncated): keep
<6,000 chars (`test_memory_budget.py`); detail in `topics/`, logs, `docs/`. **Project = `yt938-2`; read `docs/PROJECT-MAP.md` first; never a second copy (K; `test_project_map.py`).**

## 🪪 ak's identity & team (K, 2026-11-13; every agent its OWN mail 2026-11-14)
**Every tool and every agent uses its OWN mailbox, never K's** (K, 2026-11-14). ak = `ak_mail.py`
(key `ak.identity.mailbox`); each `team.py` worker = key `ak.identity.mail.<role>`
(`ak_mail.py new/show --as <role>`; `team.py mail <role> [--new]`). K's channel addresses are
**business assets** (YouTube API), not signup emails. Never sign up as K; a phone ak can't own →
**ask K**. `test_agent_own_email.py`. **Workers** (`team.py run <role>`) DO the work; panel advises.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts don't count); steer by long-form watch-hours/week +
  `retention@2min`, never raw views. **dharma = 96% of long-form watch time → concentrate there.**
- **The first 2 minutes binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** on the hook.
- **Longer is better per view** (120-min ≈ **6.0** vs 17-min ≈ 4.6 min/view). **`content/PAUSED`**
  pauses a channel's rails. **Cadence: step up, don't jump** (dharma 1→2/week; each video must differ
  or it risks "repetitious content"; never stitch Shorts into a long-form).

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order: **live API >
  real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**. Best = a
  **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai (UTC+7), 24-hour `HH:MM`** (never raw UTC). `PROGRESS.md`'s ONLY source is
  `watch_hours.json` (weekly rail) — if it lapses the headline silently freezes.
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on a spent quota → use **per-channel
  secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel `advise.py`
  (≥5). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL. `.get()+continue` on a config key is a silent killer; a test pinning a
  "recent" date to a literal goes red on its own (`test_no_pinned_recent_date.py`).
- **Repo hygiene** (`test_repo_hygiene.py`): pushing rails run `git pull --rebase` + retry; a
  shared-ledger writer needs a guard; health thresholds > the REAL cadence.

## 🧭 Traps still true (detail in `topics/05-durable-traps.md` + daily logs)
- **Rogue stream (NOT ours):** clips no manifest names = leaked token; `rogue-guard` hides each;
  root = revoke + re-consent. A guard that only marks SUCCESS can't end a loop; prefer private over
  delete. A PUT to `brandingSettings.channel` REPLACES the object → read, merge.
- **Quota:** `videos.insert` has its own pool; Data API resets **08:00 UTC**. A GITHUB_TOKEN push
  does NOT trigger a workflow → dispatch explicitly.
- **Git/CI hygiene:** racing rails → one concurrency group per channel + a union merge driver
  (`git_push_retry.sh`). A GENERATED `docs/` report (volatile header) needs ONE writer rail, else two
  regenerating it conflict (`test_report_single_writer.py`; `test_push_retry_union.py`).
- **One duration parser:** `scripts/yt_duration.py` (never raises; `P0D`/`""`/`P1DT2H`); the old
  inline regex, copy-pasted into 10 scripts, crashed a rail (`test_duration_parse.py`).
- **Long-form rails:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; a long
  hook kills retention (cap 220); never downgrade a LIVE entry. **Content dir must be per-RUN
  (`%G%V_r${GITHUB_RUN_NUMBER}`) on EVERY `%G%V` rail, and the theme must ROTATE** — else a raised
  cadence is a no-op or an add/add conflict.
- **TTS voice fallback:** the alt Thai voice (`PremwadeeNeural`) returns `NoAudioReceived` on
  EVERY retry for some texts while the house voice reads the same text fine — a per-voice refusal,
  not a socket blip; `speak()` falls back to VOICE (`test_tts_fallback.py`).
- **Every new mechanism seeds a false alarm until the sweep learns it** (qa_gate graded a 120-min B;
  counter_ledger read a dip as DOWN; a pre-08:00-UTC 403 = spent quota, not an outage).
- **Pausing a channel drops it from each rail's `matrix`; unpausing must PUT IT BACK** or the rail
  looks healthy and produces nothing (`test_rail_channels.py`).
- **Audit was blind to a take-down** (→ `find_removed`). **Mail is on the cloud, not PC1** (dead).
- **ch4 UNPAUSED 2026-11-13**: a tension hook is **enforced** (`test_hook_concrete`) for the
  long-form hook AND the Shorts pool; no "full clip" CTA (`test_ch4_cta.py`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md` · daily logs.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`, `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account — genx `kongkeat.938`, dharma `farmmer.938`, ch4
  `kongkeat.p3` (`test_channel_accounts.py`).
- **Delegation:** genx+dharma → Manager `aerismusic8@gmail.com`; ch4 BLOCKED
  (`uploadLimitExceeded` API-only; web Studio works).
- **Inviting needs K's OWNER password**: a failed save **vanishes** on reload → verify.
- **Pod env:** recycled → reinstall `ffmpeg` + `pip -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`; suite = every `scripts/test_*.py`.
- **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`).
