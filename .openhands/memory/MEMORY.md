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
- **Times to K = Thai `HH:MM`** (UTC+7); `PROGRESS.md` ← `watch_hours.json`.
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead check → **per-channel secret = identity**.
- **An LLM is not a primary source** — read the vendor's rule or measure live. **PC1 = ak's
  hands** (`winremote`, `topics/03`).
- **K ใช้มือถือ — ห้ามขอให้ K ล็อกอินผ่าน noVNC/PC1** (จอเลื่อน/ซูมไม่ได้, K ไม่พอใจ
  2026-11-22); ล็อกอินที่ต้องมี K = `yt_auth_device.py` (code + `google.com/device`).
- **ak อัพเองได้เมื่อ gate ผ่าน** (2026-11-21) — ไม่มี ledger/รออนุมัติ; gate/cap/cadence ยังผูก.
- **A gate whose floor came from the same demo it approved cannot detect drift** (720p passed
  a 4K bar for a day) — the rail must state the floor, and a test must feed it a file that fails.
- **A guard must be able to FAIL;** never hardcode the set it sweeps nor a threshold from it
  (`topics/05`). A 403 gate +`|| echo 0` = **false pass**.
- **Pod env:** reset → `pip -r requirements.txt` + static-ffmpeg (ffmpeg→`~/.local/bin` on `PATH`);
  **secret injects only if its NAME is in the command**; git identity resets. **push:** `scripts/gh_auth.py push` (token ใน KV vault
  `ak.github.token`; `git push` ตรง ๆ = 403 เพราะ gh หยิบ env token อ่านอย่างเดียวก่อน);
  suite = every `test_*.py`; **งานต้องออกจาก pod** = `durability_guard.py` + `restore_env.sh`;
  `--unshallow` before ahead/behind (`topics/05`).
- **Advisors:** `council3.py`/`advise.py`/`team.py`; วัด 2026-11-22: ตอบแค่ gemini+pollinations → retry 1.

- **MV:** ภาพใหม่ทุกคลิป, stamp `content/art_ledger_mv.json` (`make_mv.py`+`mv_run.py`); sha ซ้ำ = FAIL;
  arc 6 แบบ + เพลงห้ามซ้ำในช่อง. **เนื้อเรื่อง:** `content/content_ledger.json` (parts sha/เพลง/arc/ชื่อ) —
  `build_night.py` เจอบทเคยออกอากาศ = **exit 3**; guard `test_content_no_repeat.py`. AI gen ล่ม → procedural.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS**: `ax-workspace` auto-shorts (disabled); **rogue-guard hid 6 of our fresh clips** (manifests
  unpushed) → hide only on RSS-confirm or 24 h; `keep_clips_live.py` restores. **`videos.update` REPLACES
  the whole `snippet`/`status`**. `topics/05`.
- **Repo is PUBLIC** (private halts the rails): never commit a credential/address.
- **Quota:** `videos.insert`; reset 08:00 UTC
- **Git/CI hygiene:** racing rails → one concurrency group/channel + the union driver; a
  GENERATED `docs/` report needs ONE writer. **One duration parser** `yt_duration.py`.
- **Long-form rails** (`topics/05`): `skip` ≠ `skip_pub`; gate before queue; never downgrade a LIVE
  entry; theme rotates per RUN count. **A pod render dies ~19 min in → `longform-standard.yml`** (CI).
- **GitHub cron** fires 23/100 but late; foreman backfill = truth; rails can be `disabled_manually`
  → measure `actions/workflows` before trusting "it runs".
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar, ALL channels**: **long-form 4K 3840x2160** (K 2026-11-23: gate
  `--min-height 2160`; scenes 960px x4), Shorts 1080x1920, tv/bt709, -14 LUFS, clean grade,
  floating Thai text, 1.06x lanczos; **ONE grade `video_grade.py`** (`setparams=range=tv`).
- **K 2026-11-23: "4K เท่านั้นถึงอัพ · ห้ามซ้ำ ทั้งภาพ ดนตรี บท"** → ONE gate
  `upload_gate.py` (short ≥2160x3840, long ≥3840x2160; md5 picture, bed id, script
  n-gram ≥45% = refused). `pick_bed` HELDs a dry library instead of reusing a bed. ทุก builder 4K
  (`test_all_builders_4k.py`); `purge_sub4k.py --dirs` ลบไฟล์ <4K + dir ที่ไม่มีคลิป 4K; ไม่มี ffprobe = exit 2 BLIND.
  **ห้ามซ้ำระดับ "สร้างใหม่"**: `record_art/bed/script` (ledger, owner=spec id) — `standard_clip`
  หยุดบิลด์ถ้าภาพ/เพลงชน, `publish_shorts`/`publish_youtube` claim บทที่ `content/script_ledger_<ch>.json`;
  `writers_room.problems(..., heard)` ปฏิเสธบทซ้ำ ≥45% (`test_no_repeat_paths.py`).
- **Shorts: meet the standard or NOT upload** (backlog too). `short_standard.py`: 1080x1920 tv/bt709,
  -14 LUFS, ≤60 s, 9:16 thumb; `publish_shorts.py` gates every upload. **`alimiter` limits SAMPLE peak**: `TP_WAV` = gate − AAC overshoot, never `TP+0.3`.
- **Vision grader NON-DETERMINISTIC** → judge metrics, not CI.
- **A rail can die at IMPORT** (deps) → `test_workflow_deps.py`; a stale tree fakes "missing"
  (`git fetch` first); **ffmpeg/git inherit stdin → SIGTTIN** → `stdin=DEVNULL`.
- **Dead source read as "clean" = false pass**: RSS 404 → `UU<id>`; exits **2=BLIND**.
- **Pausing drops a channel from a rail `matrix`; unpausing must PUT IT BACK** .
- **ch4 = PCSEV = เกร็ดความรู้ "ทำไม"** (P/C/S/E/V, hook `_CURIOSITY`); family genre ปลดระวาง;
  slug ยัง `kongkeat-story`; **title ตั้งใน Studio** (API ไม่ได้).
- **Angle de-dup floor = 8** (a 3-char floor rejected all Thai runs; `test_angle_pool.py`).
  **One live title = one video**.
- **Thumb ผิดแนว (การ์ดดำ) → `--gen-art`.**
- **Thumb URL ≠ ของเรา** (AUTO frame ก็ได้ `maxresdefault`) → เช็ค 8×8 diff (`matches_live()`).
- **Animated still ต้องตรงเรื่อง**: `make_motion_short.py` แยกตาม `genre`; ส่ง `publish_motion.py` (`motion-<id>`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions (watchdog → foreman → rails), kill switch `content/STOP`; **no STOP,
  29 rails off → ak produces/uploads by hand**; NEW sys = `recovered/VIDEO-SYSTEM-NEW`. NEW sys = `recovered/VIDEO-SYSTEM-NEW`.
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account.
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 = Coverr b-roll.
- **Comment writes need `force-ssl`** (pinned Short CTA 403s).
