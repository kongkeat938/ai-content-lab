# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai; **measured, not claims**. Keep <6,000
(`test_memory_budget.py`); detail in `topics/`.
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
- **ฟอร์แมตที่ชนะ (วัดสด 2026-11-21):** คลิป niche มัธยฐาน **85.7 นาที**, ชื่อ = ปัญหา+เวลา+ผล;
  story spec `content/standard/*_story_*.json` (`kind: story`) + `test_story_specs.py`;
  90 นาที = `make_compilation.py --minutes 90`.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live**; trust **live API >
  output file (ffprobe/ebur128) > a test that can FAIL > a doc**. Best = a **counter with an invariant**
  (`counter_ledger.py`).
- **Times to K = Thai (UTC+7) `HH:MM`**; `PROGRESS.md` ← `watch_hours.json`.
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead check → **per-channel secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. **PC1 = ak's
  hands** via `winremote` (`topics/03`).
- **ak อัพเองได้เมื่อ gate ผ่าน** (2026-11-21) — ไม่มี ledger/รออนุมัติ; gate/cap/cadence ยังผูก.
- **A guard must be able to FAIL;** never hardcode the set it sweeps nor a threshold from it
  (a literal 8 d hid a rail dead 66 h, `topics/05`). A 403 gate +`|| echo 0` = **false pass**.
- **Pod env:** reset → `pip -r requirements.txt` + `pip install static-ffmpeg` (copy ffmpeg/ffprobe →
  `~/.local/bin`, prepend `PATH`); **a secret is injected only if its NAME is in the command** (else
  "Missing credentials"); git identity resets. `GH_TOKEN=$KONGKEAT_GH_TOKEN`; push 403 →
  `x-access-token:` URL; suite = every `test_*.py`; **งานต้องออกจาก pod** = `durability_guard.py` +
  `restore_env.sh`; `--unshallow` before ahead/behind (`topics/05`).
- **Advisors:** `council3.py`+`advise.py`+`team.py`; วัด 2026-11-22: ตอบแค่ `gemini`+`pollinations` →
  quorum ล้มให้ retry 1 ครั้ง (`--vendors gemini,pollinations`).

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS**: `ax-workspace` auto-shorts (K's old repo) — disabled, secrets deleted;
  `aeris` = READ-ONLY. **`videos.update` REPLACES the whole `snippet`**. `topics/05`.
- **Repo is PUBLIC** (private halts the rails): never commit a credential/address
  (`test_no_committed_{secrets,pii}.py`).
- **Quota:** `videos.insert` own pool; reset 08:00 UTC.
- **Git/CI hygiene:** racing rails → one concurrency group/channel + the union driver; a
  GENERATED `docs/` report needs ONE writer. **One duration parser** `yt_duration.py`.
- **Long-form rails** (`topics/05`): `skip` ≠ `skip_pub`; gate before queue; never downgrade a LIVE
  entry; theme rotates per RUN count; backfill needs evenly spaced crons. **A pod render dies ~19 min
  in → approved clip = `longform-standard.yml`** (CI, never uploads).
- **GitHub cron** fires 23/100 but late; foreman backfill = truth. **All rails can be `disabled_manually`
  at once (no `content/STOP`)** → measure `actions/workflows` first, re-enable + dispatch `watchdog`.
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar, ALL channels**: 1080p crf18, tv/bt709, -14 LUFS, clean grade,
  floating Thai text, 1.06x lanczos; **ONE grade source `video_grade.py`** (`setparams=range=tv`).
- **Shorts: meet the standard or NOT upload** (backlog too). `short_standard.py`: 1080x1920,
  yuv420p tv/bt709, -14 LUFS, ≤60 s, + 9:16 thumb (≥640, <2 MB); `publish_shorts.py` gates every
  upload. **`alimiter` limits SAMPLE peak → true peak plateaus above it**: `TP_WAV` = gate − AAC
  overshoot, never `TP+0.3` (`test_short_loudness.py`).
- **Vision grader NON-DETERMINISTIC**: judge by metrics, never CI.
- **A rail can die at IMPORT** (deps) → `test_workflow_deps.py`. **A stale tree fakes "missing"**
  (`git fetch` first). **ffmpeg/git inherit stdin → SIGTTIN freezes** → `stdin=DEVNULL`
  (`test_subprocess_stdin.py`).
- **Dead source read as "clean" = false pass**: `rogue_watch_rss.py` fell back to `UU<id>` on 404; exits **2=BLIND**.
- **Pausing drops a channel from a rail `matrix`; unpausing must PUT IT BACK** (`test_rail_channels.py`).
- **ch4 = PCSEV = เกร็ดความรู้/วิทยาศาสตร์ "ทำไม"** (Shorts-first, 5 ขั้น P/C/S/E/V; hook =
  คำถาม `_CURIOSITY`, `content/hooks/knowledge.md`); family/story genre **ปลดระวาง** (คิวปิด).
  slug ในโค้ดยังเป็น `kongkeat-story`. **TITLE NOT API-settable → K ตั้งใน Studio**.
- **Angle de-dup floor = 8** (a 3-char floor rejected all Thai runs; `test_angle_pool.py`).
  **One live title = one video**.
- **Thumb ผิดแนว (การ์ดดำ) → `--gen-art`.**
- **Thumb URL ≠ ของเรา** (AUTO frame ก็ได้ `maxresdefault`) → เช็ค 8×8 diff (`matches_live()`).
- **Animated still ต้องตรงเรื่อง**: `make_motion_short.py` แยกตาม `genre`; ส่ง `publish_motion.py` (`motion-<id>`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **No STOP; 29 rails disabled → ak produces manually and uploads on its own.** NEW sys →
  `recovered/VIDEO-SYSTEM-NEW/`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account.
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 = Coverr b-roll gaps.
- **Comment writes need `force-ssl`** (pinned Short CTA 403s).
