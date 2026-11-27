# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai; **measured, not claims**. Keep <6,000
(`test_memory_budget.py`); detail in `topics/` + daily logs.
**Project `yt938-2`; read `docs/PROJECT-MAP.md` first.**

## 🪪 ak's identity & team
**Every tool uses its OWN mailbox, never K's** (`test_agent_own_email.py`, `ak_mail.py`).
**Workers** (`team.py run <role>`) DO the work.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP = long-form ONLY** (Shorts don't count); steer by long-form watch-h/week + `retention@2min`.
  **dharma = 96% of long-form watch time → concentrate there.**
- **Longer is better/view** (120-min ≈ 6.0 vs 17-min ≈ 4.6). **`content/PAUSED`** pauses a channel.
  **Cadence: step up, don't jump**.
- **The first 2 min binds** (dharma 28.9%@2%, target ≥40%); fade-in 4s→1s = **+12 dB** hook.
- **ฟอร์แมตชนะ (11-21):** niche มัธยฐาน **85.7 นาที**, ชื่อ = ปัญหา+เวลา+ผล; story spec `*_story_*.json`;
  90 นาที = `make_compilation.py --minutes 90`.

## 🔑 Durable principles (K)
- **PCSEV.** Verify **live**: live API > output file (ffprobe/ebur128) > a test that FAILs > a doc;
  best = **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai `HH:MM`** (UTC+7); `PROGRESS.md` ← `watch_hours.json`
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead → **per-channel secret = identity**
- **An LLM is not a primary source** — read the vendor's rule or measure live. **PC1 = ak's
  hands** (`winremote`, `topics/03`).
- **K ใช้มือถือ — ห้ามขอให้ล็อกอินผ่าน noVNC/PC1**; ล็อกอินที่ต้องมี K = `yt_auth_device.py`.
- **ak อัพเองได้เมื่อ gate ผ่าน** (2026-11-21) — ไม่มี ledger/รออนุมัติ; gate/cap/cadence ยังผูก.
- **A gate whose floor came from the same demo it approved cannot detect drift**; a guard must be
  able to FAIL, never hardcode what it sweeps, `403 gate + || echo 0` = **false pass** (`topics/05`).
- **Pod env:** reset (idle ~2 h เป็นหลัก, mid-session ก็มี) → `pip -r requirements.txt` + static-ffmpeg;
  **secret injects only if its NAME is in the command**; git identity resets. **push:** `GH_PUSH_TOKEN=$GITHUB_TOKEN scripts/gh_auth.py push` (HEAD→main; vault token 401);
  **งานต้องออกจาก pod** = `durability_guard.py` + `restore_verify.py` (`topics/05`).

- **MV/เรื่อง:** `art_ledger_mv.json`, `content_ledger.json` (ซ้ำ = FAIL); AI gen ล่ม → procedural

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS** (`ax-workspace` auto-shorts, disabled): hide only on RSS-confirm or 24 h;
  `keep_clips_live.py` restores. **`videos.update` REPLACES the whole `snippet`/`status`**.
- **Repo is PUBLIC** (private halts the rails): never commit a credential; `yt_token*` ignored; secret-guard ไม่ wire (TODO)
- **Quota:** `videos.insert`, 08:00; 1ช่อง=1acc
- **Git/CI hygiene:** racing rails → one concurrency group/channel + the union driver; **One duration
  parser** `yt_duration.py`. GitHub cron fires late;
  a rail can be `disabled_manually` → measure `actions/workflows` first.
- **A rail can die at IMPORT** (deps) → `test_workflow_deps.py`; stale tree fakes "missing"
  (`git fetch` first); **ffmpeg/git inherit stdin → SIGTTIN** → `stdin=DEVNULL`.
- **Long-form render:** pod render dies ~19 min in → `longform-standard.yml` (CI). **Runner cap =
  150 min**; encoding 3× killed two builds (2026-11-26) → **one pass** (`picture_graph`, 2.7× realtime
  at 4K; guard `test_longform_single_pass.py`). `skip` ≠ `skip_pub`; gate before queue; never
  downgrade LIVE.
- **Dead source read as "clean" = false pass**: RSS 404 → `UU<id>`; **2=BLIND**.
- **Pausing drops a channel from a rail `matrix`; unpausing must PUT IT BACK.**
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE; edge-tts: **one request per clip**.
- **Reference look = MINIMUM bar:** long-form **4K 3840x2160** (gate `--min-height 2160`), Shorts
  **2160x3840** (`short_standard.py`, ≤60 s), tv/bt709, -14 LUFS; **ONE grade `video_grade.py`**.
- **"4K เท่านั้นถึงอัพ · ห้ามซ้ำ ทั้งภาพ ดนตรี บท"** → ONE gate `upload_gate.py` (md5 ภาพ, bed id,
  script n-gram ≥45% = refused); ไม่มี ffprobe = exit 2 BLIND; claim ตาม spec id.
- **`alimiter` limits SAMPLE peak** → `TP_WAV` = gate − AAC overshoot, never `TP+0.3`.
- **Vision grader NON-DETERMINISTIC** → judge metrics, not CI.
- **ch4 = PCSEV = เกร็ดความรู้ "ทำไม"** (P/C/S/E/V, hook `_CURIOSITY`); slug ยัง `kongkeat-story`;
  **title ตั้งใน Studio** (API ไม่ได้). **Angle de-dup floor = 8** (`test_angle_pool.py`).
  **One live title = one video.**
- **ท่อจริง = playlist** (วัด 2026-11-26): PLAYLIST 9.7–42 นาที/วิว, RELATED 6.0, SUBSCRIBER 1.1;
  **SHORTS→long = 0** ใน 28 วัน — CTA ในคลิปสั้นยังเป็น "กดติดตาม" เท่านั้น. `playlist_fill.py` เติม
  long-form ให้ครบ playlist ที่ Short ลิงก์ (`link_shorts` ครอบ Short ใหม่เท่านั้น).
  `yt_auth.load_credentials(<channel_id>)` — ไม่ส่ง = หยิบผิดช่อง.
- **Thumb:** ผิดแนว→`--gen-art`; ยอดวิวเก่า = วัด CTR ไม่ได้

- **release = tag push** → ทุก rail ที่มี `push:` รัน (`paths:` ไม่ถูกประเมินกับ tag) → ต้องมี
  `branches: [main]`; guard `test_workflow_tag_safe.py`. **pod reset ลบ pip ทั้งหมด** → static_ffmpeg.

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions (watchdog→foreman→rails), kill switch `content/STOP`; rails off →
  ak ทำมือ; NEW sys = `recovered/VIDEO-SYSTEM-NEW`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3` over **all ledger keys**
  (`test_publish_shorts_cap.py`)
- **Delegation:** genx+dharma → `ch3@…`; ch4 = Coverr
- **Comment writes need `force-ssl`**: 11-26 `commentThreads.insert` = **403 ทั้ง 4 ช่อง**; 68 Shorts ตั้งแต่ 11-12 `cta_note`=skipped ไม่เคยสำเร็จ → **SHORTS→long = 0**. token อยู่ **GitHub repo
  secrets**; `GITHUB_TOKEN` แตะไม่ได้ → **secret = K เท่านั้น** (gh expiry=?; push=HEAD→main)
- **Audit log ไม่มีคนอ่าน = ตาย:** `content/upload_audit.jsonl` ต้องมี summarize รายสัปดาห์ถ้าจะใช้จริง;
  gh token = fine-grained PAT 90 วัน + จดวันหมดอายุ (vault ว่าง = push ไม่ได้).
