# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. Keep <6,000 chars (`test_memory_budget.py`); detail in `topics/`/logs.
**Project `yt938-2`; read `docs/PROJECT-MAP.md` first (`test_project_map.py`).**

## 🪪 ak's identity & team
**Every tool uses its OWN mailbox, never K's** (`test_agent_own_email.py`); ak = `ak_mail.py`.
**Workers** (`team.py run <role>`) DO the work; panel advises.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP = long-form ONLY** (Shorts don't count); steer by long-form watch-h/week + `retention@2min`.
  **dharma = 96% of long-form watch time → concentrate there.**
- **The first 2 minutes binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** on the hook.
- **Longer is better/view** (120-min ≈ 6.0 vs 17-min ≈ 4.6). **`content/PAUSED`** pauses a channel.
  **Cadence: step up, don't jump** (else "repetitious content").

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live**; trust order **live API >
  output file (ffprobe/ebur128) > a test that can FAIL > a doc**; best = a **counter with an
  invariant** (`counter_ledger.py`).
- **Times to K = Thai (UTC+7) `HH:MM`**. `PROGRESS.md` ← `watch_hours.json` only.
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on spent quota → **per-channel secret
  = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel `advise.py`
  (≥5; openrouter/ChatGPT/deepseek/HF dead). **PC1 = ak's hands** via `winremote` (`topics/03`).
- **A guard must be able to FAIL;** never hardcode the set it sweeps; a generator that drops a piece
  must FAIL. A gate probing an API its token can't read (403)+`|| echo 0` = **false pass**.
- **Pod env:** recycled → reinstall `ffmpeg` + `pip -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`; push 403 on the credential-helper → push with
  `https://x-access-token:$KONGKEAT_GH_TOKEN@...`; suite = every `scripts/test_*.py`.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS**: `ax-workspace` auto-shorts (K's old repo); disabled, YT secrets deleted;
  `aeris` = READ-ONLY. **`videos.update` REPLACES the whole `snippet`**. `topics/05`.
- **Repo is PUBLIC** (private halts the rails): never commit a credential or a real address
  (`test_no_committed_secrets.py`, `test_no_committed_pii.py`).
- **Quota:** `videos.insert` own pool; Data API resets 08:00 UTC; a GITHUB_TOKEN push does NOT
  trigger a workflow (dispatch explicitly).
- **Git/CI hygiene:** racing rails → one concurrency group/channel + a union merge driver
  (`git_push_retry.sh`); a GENERATED `docs/` report needs one writer. **One duration parser:**
  `yt_duration.py`.
- **Long-form rails:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; hook cap
  220; never downgrade a LIVE entry. **Content dir per-RUN (`%G%V_r${GITHUB_RUN_NUMBER}`) + theme
  ROTATES** — else a raised cadence is a no-op/conflict.
- **TTS fallback:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar for ALL channels** (K, 2026-11-17): 1080p crf18, yuv420p tv/bt709,
  -14 LUFS, clean grade, floating Thai text, 1.06x lanczos. **ONE grade source `video_grade.py`**
  (`verify_night.py` hard-fails non-tv).
- **Shorts: meet the standard or NOT upload** (K, 2026-11-17), backlog too. One source
  `short_standard.py`: 1080x1920 9:16, **yuv420p tv/bt709**, -14 LUFS, ≤60 s, + a **9:16 thumbnail**
  (min height 640, <2 MB). `publish_shorts.py` gates EVERY upload, HOLDS a substandard build.
  **Loudness: pin by MEASUREMENT**, not a fixed gain (`test_short_loudness.py`).
- **Vision grader is NON-DETERMINISTIC** (same cut 9 then 5/10): never gate in CI; use metrics.
- **A rail can die at IMPORT** (deps subset; `continue-on-error` masks it) → `test_workflow_deps.py`.
- **A dead source read as "clean" = false pass** (2026-11-16): `rogue_watch_rss.py` said "no rogue"
  while `feeds/videos.xml` 404'd → falls back to `UU<id>`; exits **2=BLIND**. `topics/05`.
- **Pausing drops a channel from each rail's `matrix`; unpausing must PUT IT BACK**
  (`test_rail_channels.py`); `find_removed` confirms a take-down via oEmbed.
- **ch4 PIVOT 2026-11-16** (family → knowledge; old genre died). Hook opens a question
  (`_CURIOSITY`); `content/hooks/knowledge.md`. **Channel TITLE is NOT API-settable → K sets it in
  Studio**; the repo must FOLLOW the live name (ch4 = **"PCSEV"**), else the daily rail rewrites
  `localizations.th_TH.title` back (name labels only; genre word stays in keywords).
- **Curated angles survive de-dup** (`test_angle_pool.py`): a 3-char floor rejected every angle
  (Thai shares 3-char runs). Floor **8**.
- **One live title = one video** (`test_optimize_titles_dedup.py`): `optimize_titles` proposed
  titles per clip → 2 dharma long-form shared a title (fixed 2026-11-18).
- **A truthy thumbnail URL ≠ our image set** (2026-11-18): YT serves `maxresdefault` for an AUTO
  frame too → `set_thumbnails --skip-existing` skipped a cover-less video forever; fix =
  `matches_live()` correlates the served frame with our file.
- **An animated still beats a slide-show** (K, 2026-11-18): `make_motion_short.py` = ken-burns +
  twinkling stars + drifting leaves + a mascot dancing to the beat (`test_motion_short.py`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account (`test_channel_accounts.py`).
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 BLOCKED (`uploadLimitExceeded`).
  **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`).
