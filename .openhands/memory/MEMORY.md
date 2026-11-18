# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai; **measured, not claims**; ak decides via the
**panel** (`advise.py`), not K. Keep <6,000 (`test_memory_budget.py`); detail in `topics/`.
**Project `yt938-2`; read `docs/PROJECT-MAP.md` first (`test_project_map.py`).**

## 🪪 ak's identity & team
**Every tool uses its OWN mailbox, never K's** (`test_agent_own_email.py`); ak = `ak_mail.py`.
**Workers** (`team.py run <role>`) DO work.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP = long-form ONLY** (Shorts don't count); steer by long-form watch-h/week + `retention@2min`.
  **dharma = 96% of long-form watch time → concentrate there.**
- **Longer is better/view** (120-min ≈ 6.0 vs 17-min ≈ 4.6). **`content/PAUSED`** pauses a channel.
  **Cadence: step up, don't jump** (else "repetitious content").
- **The first 2 minutes binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** hook.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live**; trust order **live API >
  output file (ffprobe/ebur128) > a test that can FAIL > a doc**.
  Best = a **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai (UTC+7) `HH:MM`**. `PROGRESS.md` ← `watch_hours.json` only.
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on spent quota → **per-channel secret
  = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. **Panel = Gemini
  ALONE** (K, 2026-11-18); **when stuck, FOLLOW Gemini** (`test_advise_panel.py`).
  **PC1 = ak's hands** via `winremote` (`topics/03`).
- **A guard must be able to FAIL;** never hardcode the set it sweeps; a generator that drops a piece
  must FAIL. A gate probing an API its token can't read (403)+`|| echo 0` = **false pass**.
- **A test hitting a veto injects the fix seam** (`apply_qa_gate(fix=)`); default = LIVE Gemini
  + `content/fixes/`. **งานไม่ผ่าน gate → ถาม Gemini หาทางแก้** (`fix_with_gemini.py`; ไม่ล้าง veto).
  **อ่านคำตอบ Gemini = join ทุก `content.parts`** (`gemini_text.text_of`): `parts[0]` ตัดกลางคำ.
- **Pod env:** recycled → reinstall `ffmpeg` + `pip -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`; push 403 → push with `x-access-token:` URL; suite = every `test_*.py`.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS**: `ax-workspace` auto-shorts (K's old repo); disabled, YT secrets deleted;
  `aeris` = READ-ONLY. **`videos.update` REPLACES the whole `snippet`**. `topics/05`.
- **Repo is PUBLIC** (private halts the rails): never commit a credential or a real address
  (`test_no_committed_secrets.py`, `test_no_committed_pii.py`).
- **Quota:** `videos.insert` own pool; Data API resets 08:00 UTC; a GITHUB_TOKEN push does NOT trigger a run.
- **Git/CI hygiene:** racing rails → one concurrency group/channel + a union merge driver
  (`git_push_retry.sh`); a GENERATED `docs/` report needs one writer. **One duration parser:**
  `yt_duration.py`.
- **Long-form rails:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; hook cap
  220; never downgrade a LIVE entry. **Content dir per-RUN (`%G%V_r${GITHUB_RUN_NUMBER}`) + theme
  ROTATES** — else a raised cadence is a no-op/conflict.
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar, ALL channels** (K, 2026-11-17): 1080p crf18, yuv420p tv/bt709,
  -14 LUFS, clean grade, floating Thai text, 1.06x lanczos. **ONE grade source `video_grade.py`**;
  **colour tags need `setparams=...range=tv`** on re-encode (`-color_*` alone leaves trc unknown).
- **Shorts: meet the standard or NOT upload** (K, 2026-11-17), backlog too. One source
  `short_standard.py`: 1080x1920 9:16, **yuv420p tv/bt709**, -14 LUFS, ≤60 s, + a **9:16 thumbnail**
  (min height 640, <2 MB). `publish_shorts.py` gates EVERY upload, HOLDS a substandard build.
  **Loudness: pin by MEASUREMENT**, not a fixed gain (`test_short_loudness.py`).
- **Vision grader NON-DETERMINISTIC** (same cut 9 then 5/10): never gate in CI; use metrics.
- **A rail can die at IMPORT** (deps subset; `continue-on-error` masks it) → `test_workflow_deps.py`.
- **A dead source read as "clean" = false pass**: `rogue_watch_rss.py` fell back to `UU<id>` while
  `feeds/videos.xml` 404'd; exits **2=BLIND**. `topics/05`.
- **Pausing drops a channel from each rail's `matrix`; unpausing must PUT IT BACK**
  (`test_rail_channels.py`).
- **ch4 PIVOT 2026-11-16** (family → knowledge; old genre died). Hook opens a question
  (`_CURIOSITY`); `content/hooks/knowledge.md`. **Channel TITLE is NOT API-settable → K sets it in
  Studio**; the repo FOLLOWS the live name (ch4 = **"PCSEV"**).
- **Curated angles survive de-dup**: a 3-char floor rejected every angle (Thai shares 3-char runs)
  → floor **8** (`test_angle_pool.py`).
- **One live title = one video** (`test_optimize_titles_dedup.py`).
- **A truthy thumbnail URL ≠ our image set** (2026-11-18): YT serves `maxresdefault` for an AUTO
  frame too; `matches_live()` correlates the served frame with our file.
- **An animated still beats a slide-show; its LOOK must match the story** (K, 2026-11-18):
  `make_motion_short.py` layers come from the story's `genre` -- dharma/genx = calm, knowledge =
  mascot (`test_motion_short.py`).
- **Real-clip ambient video**: `make_ambient_video.py` joins `fetch_broll.py` clips → loops to
  `--minutes`, bed -14 LUFS (`test_ambient_video.py`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account (`test_channel_accounts.py`).
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 BLOCKED (`uploadLimitExceeded`);
  **comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`).
