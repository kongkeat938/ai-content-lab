# Project Memory — ak (ai-content-lab)

**ak** · owner **K** (Thai) · measured, not claims · keep <6,000 (`test_memory_budget.py`).
**Project `yt938-2`; read `docs/PROJECT-MAP.md` first**; detail in `topics/`.

## 🪪 ak's identity
**Every tool uses its OWN mailbox, never K's** (`test_agent_own_email.py`); `ak_mail.py`.
**ak decides alone** (2026-11-28): council/advise/team/panel deleted; no second opinion.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP = long-form ONLY** (Shorts don't count); steer by long-form watch-h/week + `retention@2min`.
  **dharma = 96% of long-form watch time → concentrate there.**
- **Longer is better/view** (120-min ≈ 6.0 vs 17-min ≈ 4.6). **`content/PAUSED`** pauses a channel.
  **Cadence: step up, don't jump** ("repetitious").
- **2 นาทีแรกผูกผล** (dharma 28.9%@2%, เป้า ≥40%); fade-in 4s→1s = **+12 dB**. **Shorts >48 วิ อ่อน** (คุมยุค 1.9x; genx 1.25x) → เป้า 30–45 วิ; `prefer_short` สั้นก่อน.
- **ฟอร์แมตชนะ (2026-11-21):** niche **85.7 นาที**, ชื่อ = ปัญหา+เวลา+ผล; spec
  `content/standard/*_story_*.json`; 90 นาที = `make_compilation.py --minutes 90`.

## 🔑 Durable principles (K)
- **PCSEV.** Verify **live**: live API > output file (ffprobe/ebur128) > a test that FAILs > a doc;
  best = **counter with an invariant** (`counter_ledger.py`).
- **เวลาให้ K = Thai `HH:MM`** (UTC+7); `PROGRESS.md` ← `watch_hours.json`.
- **"แยกไม่ได้" ≠ "ผิด":** quota-dead check → **per-channel secret = identity**.
- **An LLM is not a primary source** — read the vendor's rule or measure live. **PC1 = ak's
  hands** (`winremote`, `topics/03`).
- **K ใช้มือถือ — ห้ามขอให้ล็อกอินผ่าน noVNC/PC1**; ล็อกอินที่ต้องมี K = `yt_auth_device.py`.
- **ak อัพเองได้เมื่อ gate ผ่าน** (2026-11-21) — ไม่มี ledger/รออนุมัติ; gate/cap/cadence ยังผูก.
- **A gate whose floor came from the same demo it approved cannot detect drift** — a test must
  feed it a file that fails.
- **A guard must be able to FAIL;** never hardcode what it sweeps (`topics/05`);
  `403 gate + || echo 0` = **false pass**.
- **Pod env:** reset → `pip -r requirements.txt` + static-ffmpeg; **secret injects เฉพาะเมื่อชื่ออยู่ใน
  คำสั่ง**; **push:** `gh_auth.py push` (plain = 403); งานต้องออกจาก pod = `durability_guard.py`.

- **MV/เนื้อเรื่อง:** `art_ledger_mv.json`, `content_ledger.json` (sha/บทซ้ำ = FAIL); gen ล่ม → procedural.

## 🧭 Traps still true (detail in `topics/` + daily logs)
- **"Rogue" = OURS** (`ax-workspace` auto-shorts): hide only on RSS-confirm/24 h (`keep_clips_live.py`).
  **`videos.update` REPLACES the whole `snippet`/`status`** (`topics/05`).
- **Repo is PUBLIC** (private halts the rails): never commit a credential/address.
- **Quota:** `videos.insert`; reset 08:00 UTC; Shorts: **ชื่อซ้ำ = refuse** (live read).
- **Git/CI hygiene:** racing rails → one concurrency group/channel + the union driver; a
  GENERATED `docs/` report needs ONE writer. **One duration parser** `yt_duration.py`.
  `fetch-depth:1` → `pull --rebase` **128**=id lost after upload; deepen first (`git_push_retry.sh`).
- **Long-form rails** (`topics/05`): `skip` ≠ `skip_pub`; gate before queue; ห้าม downgrade LIVE;
  **pod render ตาย ~19 นาที → `longform-standard.yml`**.
- **GitHub cron** fires late; rails can be `disabled_manually` → measure `actions/workflows` first.
- **TTS:** `PremwadeeNeural` refuses some texts → `speak()` uses VOICE.
- **Reference look = MINIMUM bar**: long **3840x2160**, Shorts **2160x3840**, tv/bt709, -14 LUFS;
  **ONE grade `video_grade.py`**.
- **K 2026-11-23: "4K เท่านั้นถึงอัพ · ห้ามซ้ำ"** → ONE gate `upload_gate.py` (md5 ภาพ, bed id,
  n-gram ≥45% = refused); ไม่มี ffprobe = exit 2 BLIND (`topics/05`).
- **Shorts: meet the standard or NOT upload.** `short_standard.py` ≤60 s;
  **`alimiter` limits SAMPLE peak** → `TP_WAV` = gate − AAC overshoot, never `TP+0.3`.
- **rail ตายตอน IMPORT** → `test_workflow_deps.py`; stale tree = "missing" ปลอม (`git fetch`);
  **stdin → SIGTTIN** → `stdin=DEVNULL`; vision grader ไม่ deterministic → ดู metric.
- **Dead source read as "clean" = false pass**: RSS 404 → `UU<id>`; **2=BLIND**.
- **Pausing drops a channel from a rail `matrix`; unpausing must PUT IT BACK** .
- **ch4 = เกร็ดความรู้ "ทำไม"** (P/C/S/E/V, hook `_CURIOSITY`); slug `kongkeat-story`; title ตั้งใน
  Studio; **paused 2026-11-27** (0 วิว/6 จาก 8) — PAUSED ต้องมีทั้ง `kongkeat` + `kongkeat-story`.
- **Angle de-dup floor = 8** (`test_angle_pool.py`).
  **One live title = one video**.
- **Thumb ผิดแนว → `--gen-art`**
- **Thumb URL ≠ ของเรา** → เช็ค 8×8 diff (`matches_live()`).
- **Animated still ต้องตรงเรื่อง**: `make_motion_short.py` แยกตาม `genre` → `publish_motion.py`.

- **Client rail:** `verify_short(profile="client")` = 1080x1920; `-ss` ก่อน `-i`; `alimiter=...:level=0`.
- **release = tag push** → ทุก `push:` ต้องมี `branches: [main]` (`test_workflow_tag_safe.py`).
- **เงิน = สถานะ ไม่ใช่ยอด**: created→paid→delivered→approved; cooldown ครอบ declined.
  **CI `tests.yml`** + `restore_verify.py`; `input=`+`stdin=` ชนกัน.

- **ขายตัดต่อ (2026-11-25):** `prospect_discover.py` (robots ก่อนยิง, URL/status, 404=expired)
  → `prospects_external.json`; `proposal_draft.py` (**ไม่มี send path**, ย่อขนาดแทนลดราคา);
  ราคา canonical `content/packages.json` (A490/B750/C1590); พอร์ต live /portfolio/;
  rail `prospect-daily.yml` 09:00 ไทย. **คอขวด = คนกดส่ง offer** (asset ครบ, ไม่เคยส่ง) →
  `docs/FASTWORK-LISTING-2026-11-27.md`. **edge-tts: คำขอถี่ = NoAudioReceived** → 1/คลิป + backoff.

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md`.
- **Automation:** GH Actions (watchdog → foreman → rails); kill switch `content/STOP` (= ak ทำมือ).
  **Publishing:** `content/<ch>_{publish,shorts}.json`; `DAILY_CAP=3` ทุก ledger key (id+slug).
- **Accounts:** 1 ช่อง = 1 Google account.
- **Delegation:** genx+dharma → Manager `ch3@example.invalid`; ch4 = Coverr b-roll.
- **Comment writes need `force-ssl`** (pinned Short CTA 403s).
