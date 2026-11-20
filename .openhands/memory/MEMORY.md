# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai; **measured, not claims**; ak decides via the
**panel** (`advise.py`). Keep <6,000 (`test_memory_budget.py`); detail in `topics/`.
**Project `yt938-2`; read `docs/PROJECT-MAP.md` first.**

## 🪪 ak's identity & team
**Every tool uses its OWN mailbox, never K's** (`test_agent_own_email.py`); `ak_mail.py`.
**Workers** (`team.py run <role>`) DO the work.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP = long-form ONLY** (Shorts don't count); steer by long-form watch-h/week + `retention@2min`.
  **dharma = 96% of long-form watch time → concentrate there.**
- **Longer is better/view** (120-min ≈ 6.0 vs 17-min ≈ 4.6). **`content/PAUSED`** pauses a channel.
  **Cadence: step up, don't jump** ("repetitious").
- **The first 2 min binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** hook.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live**; trust **live API >
  output file (ffprobe/ebur128) > a test that can FAIL > a doc**. Best = a **counter with an invariant**
  (`counter_ledger.py`).
- **Times to K = Thai (UTC+7) `HH:MM`**. `PROGRESS.md` ← `watch_hours.json`.
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead identity check → **per-channel secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. **Panel = Gemini
  ALONE** (K, 2026-11-18); **when stuck, FOLLOW Gemini** (`test_advise_panel.py`). **PC1 = ak's
  hands** via `winremote` (`topics/03`).
- **งานไม่ผ่าน Gemini = K ห้ามอัพ** (2026-11-19): โค้ดทุกไฟล์ต้องมี APPROVE ใน
  `docs/reviews/ledger.json` (digest = ที่ Gemini เห็น; แก้ 1 ไบต์ = stale; baseline = **หนี้**).
- **A guard must be able to FAIL;** never hardcode the set it sweeps nor a threshold from it
  (a literal 8 d hid a rail dead 66 h, `topics/05`). A 403 gate +`|| echo 0` = **false pass**.
- **Veto test injects the fix seam** (`apply_qa_gate(fix=)`; LIVE Gemini → `fix_with_gemini.py`). **อ่าน Gemini = join ทุก `content.parts`** (`gemini_text.text_of`).
- **Pod env:** recycled → `ffmpeg` + `pip -r requirements.txt`; `GH_TOKEN=$KONGKEAT_GH_TOKEN`;
  push 403 → `x-access-token:` URL; suite = every `test_*.py`. **Set the union driver
  before `git pull`** (fresh pod has none) and **`--unshallow` before reading ahead/behind**
  (`topics/05`).

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS**: `ax-workspace` auto-shorts (K's old repo) — disabled, secrets deleted;
  `aeris` = READ-ONLY. **`videos.update` REPLACES the whole `snippet`**. `topics/05`.
- **Repo is PUBLIC** (private halts the rails): never commit a credential or address
  (`test_no_committed_{secrets,pii}.py`).
- **Quota:** `videos.insert` own pool; reset 08:00 UTC; token push ≠ run.
- **Git/CI hygiene:** racing rails → one concurrency group/channel + the union driver; a
  GENERATED `docs/` report needs ONE writer. **One duration parser** `yt_duration.py`.
- **Long-form rails:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; hook cap
  220; never downgrade a LIVE entry. **Theme ROTATES per-RUN count, NEVER `date +%V`**. **Backfill
  `7/n+1` needs EVENLY spaced crons** (Mon/Wed/Fri, not Mon/Wed/Thu).
- **GitHub cron** fires 23/100 but late; foreman backfill = truth.
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar, ALL channels**: 1080p crf18, tv/bt709, -14 LUFS, clean grade,
  floating Thai text, 1.06x lanczos. **ONE grade source `video_grade.py`**; colour tags need
  **`setparams=range=tv`** on re-encode.
- **Shorts: meet the standard or NOT upload**, backlog too. One source `short_standard.py`:
  1080x1920 9:16, **yuv420p tv/bt709**, -14 LUFS, ≤60 s, + **9:16 thumbnail** (min 640, <2 MB).
  `publish_shorts.py` gates EVERY upload, HOLDS a substandard build. Loudness pinned by
  **MEASUREMENT** (`test_short_loudness.py`). **`alimiter` limits SAMPLE peak → true peak
  plateaus above it**: `TP_WAV` = gate − AAC overshoot, never `TP+0.3`.
- **Vision grader NON-DETERMINISTIC** (9 then 5/10): judge by metrics, never in CI.
- **A rail can die at IMPORT** (deps) → `test_workflow_deps.py`. **A stale tree fakes "missing"**:
  a live video not in a manifest may be a rail upload not yet pulled — `git fetch` first.
  **ffmpeg/git inherit stdin → SIGTTIN freezes the run** (state TNl):
  `stdin=subprocess.DEVNULL` (`test_subprocess_stdin.py`).
- **Dead source read as "clean" = false pass**: `rogue_watch_rss.py` fell back to `UU<id>` while
  `feeds/videos.xml` 404'd; exits **2=BLIND**.
- **Pausing drops a channel from a rail `matrix`; unpausing must PUT IT BACK** (`test_rail_channels.py`).
- **ch4 PIVOT 2026-11-16** (family → knowledge). Hook opens a question (`_CURIOSITY`);
  `content/hooks/knowledge.md`. **TITLE NOT API-settable → K sets it in Studio**; repo follows
  the live name (ch4 = **"PCSEV"**).
- **Curated angles survive de-dup**: a 3-char floor rejected all (Thai 3-char runs) → floor
  **8** (`test_angle_pool.py`). **One live title = one video**.
- **Thumb ผิดแนว = สร้างจากเฟรม (การ์ดดำ)** → `--gen-art` + **ศิลป์เปล่า**.
- **A truthy thumb URL ≠ our image set**: YT serves `maxresdefault` for an AUTO frame too;
  `matches_live()` correlates.
- **Animated still LOOK must match the story**: `make_motion_short.py` layers by `genre`; ship
  via `publish_motion.py` (**`motion-<id>`**, story ids collide with the pool's).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account (`test_channel_accounts.py`).
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 = Coverr b-roll gaps, not upload cap.
- **Comment writes need `force-ssl`**; pinned Short CTA 403s until then.
