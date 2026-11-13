# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. **This file is a MAP** (injected each session, tail truncated):
keep <6,000 chars (`test_memory_budget.py`); detail in `topics/`, logs, `docs/`.
**Project = `yt938-2`; read `docs/PROJECT-MAP.md` first. Search before creating — never make a
second copy under a new name (K, 2026-11-13; `test_project_map.py`).**

## 🪪 ak's identity & team (K, 2026-11-13)
ak **owns a mailbox** (`ak_mail.py`): use it, never K's; **never sign up as K**; a phone ak can't
own → **ask K**. **Workers** (`team.py run <role>`) DO the work; the panel (`advise.py`) only advises.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts don't count). Steer by long-form watch-hours/week +
  `retention@2min`, never raw views. **dharma = 96% of long-form watch time → concentrate there**
 (genx 6.3h, kongkeat 0.7h / 28d). **Cadence is the lever, but step up, don't jump** (panel
  2026-11-13): dharma 1→2/week; each video must differ (rotated theme, fresh set, unique bed) or it
  risks YouTube "repetitious content"; NEVER stitch high-view Shorts into a long-form (spam).
- **The first 2 minutes is the binding constraint** (dharma 28.9%@2%, target ≥40%). **Fade-in 4s→1s**
  = **+12 dB** in the opening second — the hook is the lever.
- **Watch-time/view rises with length:** 120-min ≈ **6.0** vs 17-min ≈ 4.6 min/view — keep videos
  long. **`content/PAUSED`** pauses a channel's rails (`test_paused_channel.py`).

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order:
  **live API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**.
  Best = a **counter with an invariant** (`scripts/counter_ledger.py`).
- **Times to K = Thai (UTC+7), 24-hour `HH:MM`** (never raw UTC).
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on a spent quota → use **per-channel
  secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel `advise.py`
  (≥5). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL. `.get()+continue` on a config key is a silent killer.
- **Repo hygiene** (`test_repo_hygiene.py`): pushing rails run `git pull --rebase`; a shared-ledger
  writer needs a guard; health thresholds must exceed the REAL cadence; every rail watched.

## 🧭 Traps still true (detail in `topics/05-durable-traps.md` + daily logs)
- **Rogue stream (NOT ours):** clips no manifest names = leaked token; `rogue-guard` hides each; root = revoke + re-consent.
- **A guard that only marks SUCCESS can't end a loop**; prefer private over delete. **A PUT to
  `brandingSettings.channel` REPLACES the object** → read, merge.
- **Quota:** `videos.insert` has its own pool; Data API resets **08:00 UTC**. A GITHUB_TOKEN push
  does NOT trigger a workflow → dispatch explicitly.
- **Racing jobs lose records** → one concurrency group per channel + a union merge driver for
  append-only ledgers, REGISTERED in `git_push_retry.sh` (`test_push_retry_union.py`).
- **Night rail:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; a long hook
  kills retention (cap 220); never downgrade a LIVE entry. **Content dir must be per-RUN
  (`%G%V_r${GITHUB_RUN_NUMBER}`) on EVERY `%G%V` rail (night + genx + ch4) and the learned theme
  must ROTATE, not always `themes[0]`** — else a raised cadence is a no-op, repeats, or add/add
  conflicts on the same weekly folder (`test_night_scripts.py`, `test_per_run_content_dir.py`).
- **TTS voice fallback:** the alt Thai voice (VOICE_ALT `PremwadeeNeural`, the stalled-channel
  probe) returns `NoAudioReceived` on EVERY retry for some texts while the house voice reads the
  same text fine — a per-voice refusal, not a socket blip, so retrying the same voice never
  recovers it. `speak()` falls back to VOICE (`test_tts_fallback.py`).
- **Every new mechanism seeds a false alarm until the sweep learns it** (qa_gate graded 120-min B;
  counter_ledger read a dip as DOWN; health flagged paused rails).
- **Pausing a channel drops it from each rail's `matrix`; unpausing must PUT IT BACK** or the rail
  looks healthy and produces nothing (2026-11-13 ch4; `test_rail_channels.py`).
- **Audit was blind to a take-down** (diffed only channel→manifest → `find_removed`). **Mail is on
  the cloud, not PC1** (dead); `IMAP_ACCOUNTS` = kongkeat.938 only.
- **ch4 UNPAUSED 2026-11-13** (K: "ลุย ch4"): a tension hook is **enforced** (`test_hook_concrete`)
  for the long-form hook AND the Shorts pool; no "full clip" CTA (`test_ch4_cta.py`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md` · daily logs.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_publish.json`/`_shorts.json`, `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account — genx `kongkeat.938`, dharma `farmmer.938`, ch4
  `kongkeat.p3`; `test_channel_accounts.py`. Invite = Studio → สิทธิ์ → เชิญ.
- **Delegation:** genx+dharma → Manager `aerismusic8@gmail.com`; kongkeat-story BLOCKED (2026-11-13
  `uploadLimitExceeded` API-only; web Studio works). → `topics/05`.
- **Inviting needs the OWNER's password** (K): save → Google "ยืนยันว่าเป็นคุณ"; a pending row
  **vanishes** on reload if the save failed → verify by reloading.
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`; suite = run every `scripts/test_*.py`.
- **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`); text must fit its frame;
  pinned CTA comment = the conversion lever.
