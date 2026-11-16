# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. **This file is a MAP** (injected each session, tail truncated): keep
<6,000 chars (`test_memory_budget.py`); detail in `topics/`/logs/`docs/`. **Project = `yt938-2`;
read `docs/PROJECT-MAP.md` first; never a second copy (K; `test_project_map.py`).**

## 🪪 ak's identity & team
**Every tool/agent uses its OWN mailbox, never K's** (`test_agent_own_email.py`): ak = `ak_mail.py`;
worker = `ak.identity.mail.<role>`. K's channel addresses are business assets, not signup emails.
**Workers** (`team.py run <role>`) DO the work; panel advises.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts don't count); steer by long-form watch-hours/week +
  `retention@2min`, not raw views. **dharma = 96% of long-form watch time → concentrate there.**
- **The first 2 minutes binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** on the hook.
- **Longer is better per view** (120-min ≈ **6.0** vs 17-min ≈ 4.6 min/view). **`content/PAUSED`**
  pauses a channel. **Cadence: step up, don't jump** (each video must differ or it risks
  "repetitious content").

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order:
  **live API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed
  doc**. Best = a **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai (UTC+7) `HH:MM`**. `PROGRESS.md`'s ONLY source is `watch_hours.json` (weekly rail).
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on a spent quota → **per-channel
  secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel
  `advise.py` (≥5; openrouter/ChatGPT/DeepSeek/Devin/HF all dead — don't retry). **PC1 = ak's
  hands** via `winremote` 8090/Tailscale (`topics/03`); AX stack off. **Close PC1 windows** (K).
- **A guard must be able to FAIL;** never hardcode the set it sweeps; a generator that can drop
  a piece must FAIL. `.get()+continue` on a config key is a silent killer
  (`test_no_pinned_recent_date.py`). A gate that probes an API its own token cannot read (403)
  + `|| echo 0` is a **false pass** — use an explicit opt-in that DEFAULTS OFF.
- **Repo hygiene** (`test_repo_hygiene.py`): pushing rails `git pull --rebase`+retry; a shared-ledger
  writer needs a guard; health thresholds > real cadence.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS** (2026-11-15): the 2nd uploader was `ax-workspace` auto-shorts (K's OLD
  repo) — same channels/tokens. FIXED: disabled + deleted its 5 YT secrets; `aeris` = READ-ONLY.
  **`videos.update` REPLACES the whole `snippet`** (read-merge-write). `topics/05`.
- **Repo is PUBLIC** (private would halt the rails): never commit a credential
  (`test_no_committed_secrets.py`) or a real address (`test_no_committed_pii.py`); real ones live
  in `CH_ACCOUNTS`; labels use `public_address()`.
- **Quota:** `videos.insert` own pool; Data API resets 08:00 UTC; a GITHUB_TOKEN push
  does NOT trigger a workflow (dispatch explicitly).
- **Git/CI hygiene:** racing rails → one concurrency group/channel + a union merge driver
  (`git_push_retry.sh`); a GENERATED `docs/` report needs ONE writer (`test_report_single_writer.py`).
- **One duration parser:** `scripts/yt_duration.py` (never raises; `P0D`/`P1DT2H`; `test_duration_parse.py`).
- **Long-form rails:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; a long
  hook kills retention (cap 220); never downgrade a LIVE entry. **Content dir per-RUN
  (`%G%V_r${GITHUB_RUN_NUMBER}`) on EVERY `%G%V` rail + theme ROTATES** — else a raised cadence
  is a no-op or an add/add conflict.
- **TTS fallback:** `PremwadeeNeural` refuses some texts → `speak()` falls back to VOICE
  (`test_tts_fallback.py`).
- **A rail can die at IMPORT: its workflow installs a SUBSET of the deps its script needs,
  and `continue-on-error` turns it green.** Twice (`fetch-music` no `numpy`;
  `restore-wrongly-hidden` no `google-auth-oauthlib`). `test_workflow_deps.py` sweeps it.
- **Every new mechanism seeds a false alarm until the sweep learns it** (pre-08:00-UTC 403 = quota).
- **A dead source read as "clean" = false pass** (2026-11-16): `rogue_watch_rss.py` said "no
  live rogue" while `feeds/videos.xml` 404'd → falls back to uploads playlist `UU<id>`; exits
  **2=BLIND** (≠0). `topics/05`.
- **Pausing a channel drops it from each rail's `matrix`; unpausing must PUT IT BACK**
  (`test_rail_channels.py`). **Audit blind to a take-down** (→ `find_removed`). Mail=cloud, not PC1.
- **ch4 PIVOT 2026-11-16** (family → knowledge, genre "เกร็ดความรู้รอบตัว"): old genre died
  (0.7 long-form watch-h/28d, 5.2% AVD). Hook must open a question (`_CURIOSITY`, not
  `_TENSION`); hook `content/hooks/knowledge.md`; `ch4-realign.yml` renames in place.
- **Curated angles must survive de-dup** (`test_angle_pool.py`): a 3-char floor rejected EVERY
  curated angle (dharma 0/41); Thai shares 3-char runs. Floor **8** (`fresh_angles`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md` · daily logs.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`, `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account — `ch1` genx, `ch2` dharma, `ch4` ch4 (`test_channel_accounts.py`).
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 BLOCKED (`uploadLimitExceeded`,
  API-only; web Studio works).
- **Pod env:** recycled → reinstall `ffmpeg` + `pip -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`; suite = every `scripts/test_*.py`.
- **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`).
