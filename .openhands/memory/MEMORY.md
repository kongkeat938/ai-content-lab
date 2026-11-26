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
- **PCSEV.** Verify **live**: live API > output file (ffprobe/ebur128) > a test that FAILs > a doc;
  best = **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai `HH:MM`** (UTC+7); `PROGRESS.md` ← `watch_hours.json`.
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead check → **per-channel secret = identity**.
- **An LLM is not a primary source** — read the vendor's rule or measure live. **PC1 = ak's
  hands** (`winremote`, `topics/03`).
- **K ใช้มือถือ — ห้ามขอให้ล็อกอินผ่าน noVNC/PC1**; ล็อกอินที่ต้องมี K = `yt_auth_device.py`.
- **ak อัพเองได้เมื่อ gate ผ่าน** (2026-11-21) — ไม่มี ledger/รออนุมัติ; gate/cap/cadence ยังผูก.
- **A gate whose floor came from the same demo it approved cannot detect drift** — a test must
  feed it a file that fails.
- **A guard must be able to FAIL;** never hardcode what it sweeps (`topics/05`);
  `403 gate + || echo 0` = **false pass**.
- **Pod env:** reset → `pip -r requirements.txt` + static-ffmpeg; **secret injects only if its NAME is
  in the command**; git identity resets. **push:** `scripts/gh_auth.py push` (plain `git push` = 403);
  **งานต้องออกจาก pod** = `durability_guard.py` + `restore_verify.py` (`topics/05`).
- **Advisors:** `council3.py`/`advise.py`/`team.py`.

- **MV/เนื้อเรื่อง:** `art_ledger_mv.json`, `content_ledger.json` (sha ซ้ำ = FAIL; บทซ้ำ = exit 3);
  AI gen ล่ม → procedural.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS** (`ax-workspace` auto-shorts, disabled): hide only on RSS-confirm or 24 h;
  `keep_clips_live.py` restores.
  **`videos.update` REPLACES the whole `snippet`/`status`** (`topics/05`).
- **Repo is PUBLIC** (private halts the rails): never commit a credential/address.
- **Quota:** `videos.insert`; reset 08:00 UTC
- **Git/CI hygiene:** racing rails → one concurrency group/channel + the union driver; a
  GENERATED `docs/` report needs ONE writer. **One duration parser** `yt_duration.py`.
- **Long-form rails** (`topics/05`): `skip` ≠ `skip_pub`; gate before queue; never downgrade a LIVE
  entry. **A pod render dies ~19 min in → render in `longform-standard.yml`**.
- **GitHub cron** fires late; rails can be `disabled_manually` → measure `actions/workflows` first.
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar**: long-form **4K 3840x2160** (gate `--min-height 2160`), Shorts
  1080x1920, tv/bt709, -14 LUFS; **ONE grade `video_grade.py`** (`setparams=range=tv`).
- **"4K เท่านั้นถึงอัพ · ห้ามซ้ำ ทั้งภาพ ดนตรี บท"** → ONE gate `upload_gate.py` (md5 ภาพ, bed id,
  script n-gram ≥45% = refused); ไม่มี ffprobe = exit 2 BLIND; claim ตาม spec id (`topics/05`).
- **Shorts: meet the standard or NOT upload.** `short_standard.py` 2160x3840, -14 LUFS, ≤60 s;
  **`alimiter` limits SAMPLE peak** → `TP_WAV` = gate − AAC overshoot, never `TP+0.3`.
- **Vision grader NON-DETERMINISTIC** → judge metrics.
- **A rail can die at IMPORT** (deps) → `test_workflow_deps.py`; stale tree fakes "missing"
  (`git fetch` first); **ffmpeg/git inherit stdin → SIGTTIN** → `stdin=DEVNULL`; vision grader
  NON-DETERMINISTIC → judge metrics, not CI.
- **Dead source read as "clean" = false pass**: RSS 404 → `UU<id>`; **2=BLIND**.
- **Pausing drops a channel from a rail `matrix`; unpausing must PUT IT BACK** .
- **ch4 = PCSEV = เกร็ดความรู้ "ทำไม"** (P/C/S/E/V, hook `_CURIOSITY`); family genre ปลดระวาง;
  slug ยัง `kongkeat-story`; **title ตั้งใน Studio** (API ไม่ได้).
- **Angle de-dup floor = 8** (`test_angle_pool.py`). **One live title = one video**.
- **ท่อจริง = playlist** (วัด 2026-11-26): PLAYLIST 9.7–42 นาที/วิว, RELATED 6.0, SUBSCRIBER 1.1;
  **SHORTS→long = 0** ใน 28 วัน. `playlist_fill.py` เติม long-form ให้ครบ playlist ที่ Short ลิงก์
  (`link_shorts` ครอบ Short ใหม่เท่านั้น). `yt_auth.load_credentials(<channel_id>)` — ไม่ส่ง = หยิบผิดช่อง.
- **Thumb ผิดแนว → `--gen-art`.**
- **Thumb URL ≠ ของเรา** (AUTO frame ก็ได้ `maxresdefault`) → เช็ค 8×8 diff (`matches_live()`).
- **Animated still ต้องตรงเรื่อง**: `make_motion_short.py` แยกตาม `genre` → `publish_motion.py`.

- **Client rail:** `verify_short(profile="client")` = 1080x1920; `-ss` ก่อน `-i`; `alimiter=...:level=0`.
- **release = tag push** → `push` rail ทุกตัวรัน (`paths:` ไม่ถูกประเมินกับ tag) → ทุก `push:` ต้องมี
  `branches: [main]`; guard `test_workflow_tag_safe.py` (parse YAML ไม่ใช่ regex). **pod reset ระหว่าง
  เทิร์นลบ pip ทั้งหมด** (ffmpeg/PIL/pyyaml) → static_ffmpeg add_paths + `pip -r requirements.txt`.
- **เงิน = สถานะ ไม่ใช่ยอด**: created→paid→delivered→approved; `report` นับเฉพาะที่รับ; cooldown
  ครอบ declined. **CI `tests.yml`** (suite ไม่ใช้ secret) + `restore_verify.py`; `input=`+`stdin=` ชนกัน.

- **ขายตัดต่อ (2026-11-25):** `prospect_discover.py` (robots ก่อนยิง, URL/status, 404=expired)
  → `prospects_external.json`; `proposal_draft.py` (**ไม่มี send path**, ย่อขนาดแทนลดราคา);
  ราคา canonical `content/packages.json` (A490/B750/C1590); พอร์ต live /portfolio/;
  rail `prospect-daily.yml` 09:00 ไทย. **edge-tts: คำขอยาวครั้งเดียวเวิร์ก, หลายคำขอสั้นติดกัน
  = NoAudioReceived** → 1 request/คลิป + backoff, ล้ม = FAIL.

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions (watchdog → foreman → rails), kill switch `content/STOP`; **no STOP,
  29 rails off → ak produces/uploads by hand**; NEW sys = `recovered/VIDEO-SYSTEM-NEW`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3` counted over **all ledger
  keys** (id + slug; `test_publish_shorts_cap.py`).
- **Accounts:** 1 ช่อง = 1 Google account.
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 = Coverr b-roll.
- **Comment writes need `force-ssl`** (pinned Short CTA 403s).
