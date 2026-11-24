# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai; **measured, not claims**. Keep <6,000
(`test_memory_budget.py`); detail in `topics/`. **Project `yt938-2`; read `docs/PROJECT-MAP.md` first.**

## 🪪 ak's identity & team
**Every tool uses its OWN mailbox, never K's** (`test_agent_own_email.py`, `ak_mail.py`);
**workers** `team.py run <role>` DO the work.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP = long-form ONLY**; steer by long-form watch-h/week + `retention@2min`; **dharma = 96% of
  long-form watch → concentrate there.**
- **Longer = better/view** (120-min ≈ 6.0 vs 17-min ≈ 4.6); **`content/PAUSED`** pauses a channel;
  cadence: step up.
- **The first 2 min binds** (dharma 28.9%@2%, ≥40% target); fade-in 4s→1s = **+12 dB**.
- **Winning clip (2026-11-21): median 85.7 min**, title = problem+time+result;
  `content/standard/*_story_*.json`; 90 min = `make_compilation.py --minutes 90`.

## 🔑 Durable principles (K)
- **PCSEV**; verify **live**: live API > output file (ffprobe/ebur128) > a test that can FAIL > a doc;
  best = a **counter with an invariant** (`counter_ledger.py`).
- **Times to K = Thai `HH:MM`**; `PROGRESS.md` ← `watch_hours.json`
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead check → per-channel secret = identity
- **An LLM is not a primary source**; **PC1 = ak's hands** (`winremote`, `topics/03`).
- **K ใช้มือถือ — ห้ามขอให้ K ล็อกอินผ่าน noVNC/PC1** → `yt_auth_device.py` (`google.com/device`).
- **ak อัพเองได้เมื่อ gate ผ่าน**; gate/cap/cadence ยังผูก.
- **A guard must FAIL**; never hardcode the set it sweeps nor a threshold from it (`topics/05`);
  `|| echo 0` on a 403 gate = **false pass**; a floor from the approved demo can't see drift.
- **Pod env:** reset → `pip -r requirements.txt` + static-ffmpeg (ffmpeg→`~/.local/bin`);
  **secret injects only if its NAME is in the command**; **push = `gh_auth.py push`** (`git push`
  ตรง = 403: gh ส่ง env token อ่านเดียวก่อน); suite = every `test_*.py`;
  งานต้องออกจาก pod = `durability_guard.py` + `restore_env.sh`; `--unshallow` (`topics/05`).

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS**: a stale (unpushed) manifest makes BOTH the RSS watcher and the audit call our
  fresh clips rogue → **only a clip unrecorded ≥24 h may be paused**, never on "confirmation"
  (2026-11-24: it hid a 7-min-old Short + a dharma long-form); `keep_clips_live.py`.
  **`videos.update` REPLACES the whole `snippet`/`status`** (`topics/05`).
- **Repo PUBLIC** (private halts the rails): never commit a credential/address
- **Git/CI:** racing rails → one concurrency group/channel + union driver; a GENERATED `docs/` report
  needs ONE writer; one duration parser `yt_duration.py`; **an unpushed pod = stale manifest in CI**.
- **Long-form rails** (`topics/05`): `skip` ≠ `skip_pub`; gate before queue; never downgrade a LIVE
  entry; theme per RUN count; **a pod render dies ~19 min in → `longform-standard.yml`**
- **GitHub cron** fires 23/100 late; rails can be `disabled_manually` → measure
  `actions/workflows` first. 2026-11-24: 27 off; `publish-shorts` 3×/day + `grow-shorts-pool` on.
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Look = MINIMUM bar, ALL channels**: long-form **4K 3840x2160**, Shorts **2160x3840**, tv/bt709,
  -14 LUFS, clean grade, floating Thai text, 1.06x lanczos; **ONE grade `video_grade.py`** — a
  verifier reads the size FROM it, never a literal (a `1920x1080` literal failed every 4K render).
- **Design constants scale with the canvas** (`SCALE = W/1080`): without it a 4K switch halved every
  star/text/mascot and the motion fell under its floors (`test_motion_short.py`).
- **"4K เท่านั้นถึงอัพ · ห้ามซ้ำ ทั้งภาพ ดนตรี บท"** → ONE gate `upload_gate.py` (md5 picture, bed id,
  script n-gram ≥45%); `test_all_builders_4k.py`; `purge_sub4k.py --dirs`; no ffprobe = exit 2 BLIND;
  ตอนสร้าง: `record_art/bed/script` claim ตาม spec id; `standard_clip` หยุดถ้าชน;
  `script_ledger_<ch>.json`; `writers_room` ปฏิเสธ ≥45% (`test_no_repeat_paths.py`).
- **MV:** ภาพใหม่ทุกคลิป (`art_ledger_mv.json`, `make_mv.py`); sha ซ้ำ = FAIL; arc 6 + เพลงห้ามซ้ำ;
  `build_night.py` เจอบทเคยออกอากาศ = **exit 3** (`test_content_no_repeat.py`).
- **Shorts: meet the standard or NOT upload**; `alimiter` limits SAMPLE peak →
  `TP_WAV` = gate − AAC overshoot; **a publish records its `privacy`** and is verified by
  `privacyStatus`/views moving, not by a manifest row.
- **A rail can die at IMPORT** → `test_workflow_deps.py`; a stale tree fakes "missing" (`git fetch`);
  **ffmpeg/git inherit stdin → SIGTTIN** → `stdin=DEVNULL`.
- **Dead source read as clean = false pass** (RSS 404 → `UU<id>`); **exit 2 = BLIND**
- **Pausing drops a channel from a rail `matrix`; unpause must PUT IT BACK.**
- **ch4 = PCSEV = เกร็ดความรู้ "ทำไม"** (hook `_CURIOSITY`); family genre ปลดระวาง; slug ยัง
  `kongkeat-story`; **title ตั้งใน Studio**.
- **Angle de-dup floor = 8**; **one live title = one video** (`test_angle_pool.py`)
- **Thumb ผิดแนว (การ์ดดำ) → `--gen-art`**; **thumb URL ≠ ของเรา** (AUTO frame ก็ได้ maxresdefault →
  8×8 diff `matches_live()`).
- **Animated still ตรงเรื่อง**: `make_motion_short.py` แยกตาม `genre`; ส่ง `publish_motion.py` (`motion-<id>`)
- **Kinetic base must MOVE**: 4K x264 erases grain → pan a crop window (`BASE_PAD`); a flat-colour
  fixture hides motion — test with texture.

## 🗺️ Topic map
- `topics/*.md` · `docs/DECISION-*` · `docs/HEALTH.md`.
- **Automation:** GH Actions (watchdog → foreman → rails), kill switch `content/STOP`; **no STOP,
  29 rails off → ak produces/uploads by hand**; NEW sys = `recovered/VIDEO-SYSTEM-NEW/`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3` over **all ledger keys**
  (id + slug; `test_publish_shorts_cap.py`); quota reset 08:00 UTC.
- **1 channel = 1 Google account.**
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 = b-roll.
- **Comment writes need `force-ssl`** (pinned Short CTA 403s).
