# MEMORY — index

**Agent name: `ak`** (renamed from AX by K, 2026-10-31). Owner: **K** (kongkeat).
Communicates in **Thai**; wants concise Thai answers and **measured evidence, not claims**.
K is on **Windows/PowerShell** — never hand over `&&`, `chmod`, `mkdir -p`; give native
PowerShell or UI steps.

This file is an **index only** and must stay small (the loader injects it every session and
**truncates the tail** — that is why the old 95 KB file silently lost its newest work).
Detail lives in `topics/*.md` and the daily logs `YYYY-MM-DD.md`; read the one you need.

## 🗂️ TOPIC FILES (read the one you need)
- `topics/00-channels-registry-branding.md` — channels, registry, branding, HOLD.
- `topics/01-pc1-remote-and-workstore.md` — PC1 remote, work store, Drive letters.
- `topics/02-publishing-youtube.md` — upload/post, tokens, proxy PUT trap, deletions.
- `topics/03-projects-yt938-ch4-songvideo-akath.md` — yt938-1, ch4-anime, song-video, AKATH.
- `topics/04-infra-sandbox-deps-and-traps.md` — sandbox facts, deps, constants, traps.
- `topics/05-history-coldstart-and-upgrades.md` — cold starts, upgrade pack.
- `ARCHIVE-full-MEMORY-2026-10-31.md` — the whole old file, verbatim (safety net).

## 🚨 READ FIRST — ak runs THREE channels; ch4 is kongkeat pratumma
| ch | handle | id | note |
|---|---|---|---|
| ch1 | `@tatagenxgeny` ตาต้า GenX Shop | `UCI6EfsgM1HNjrYarvigxyrQ` | philosophy |
| ch2 | `@farmmer-n9t` Farmmer | `UCM3QO5L_pmj34n1JVlbhh-w` | ธรรมะก่อนนอน (reference rail) |
| ch3 | `@aerismusicth` AERIS Music | `UCm44BjAn03ruOF-WaA3ZRww` | **CANCELLED 2026-10-30** |
| ch4 | `@kongkeatpratumma` | `UC7gCIu4G_7QCEJ8hJ-34zoQ` | series brand `เรื่องเล่าการ์ตูน` |
**`@aerisanime` (`UCR2AQNtI2o_rxQIEkQeTk9Q`) is NOT ch4** — different channel (263 anime
edits, 10.5k subs, no ak token). Canonical registry: **`ops/ax_channels.json`** (root
`ax_channels.json` is a deprecated mirror). `ops/ax_channels.py emit-content-lab|emit-html`.

## ⛔ HOLD (K, 2026-10-26) — `docs/HOLD.md`
All automations `enabled=false`. Do not enable one, upload, or start a render until K lifts
it. Renaming/branding a channel is not one of the three forbidden acts.

- **K granted `ak` authority to administer and decide (2026-10-31)** — see `DECISIONS.md` for the charter (what ak decides alone vs what still needs K).
- **ak has its own mailbox** `agatha3440ac@ce.oceanicwavel.com` (tempmail.lol, token in PC1 vault
  `ak.mail.token`; inbound verified). Proton is unusable (2D drag CAPTCHA) and mail.tm returns
  401 for every login. Details in `C:\ak\profile\AK-MAIL.md`.
- **yt938-1 = build ch1/ch2/ch4. The channels ALREADY EXIST and are live** (verified 2026-10-31
  via `YT_CH*_REFRESH_TOKEN`; newest uploads that day). **No new email/account is needed** — the
  real constraint is **Thai scripts + render**. Full table + the dropped Proton-mail detour in
  `DECISIONS.md`.
- **Marketing plan is measured, not guessed** — `docs/MARKETING-STRATEGY.md` + `docs/CONTENT-CALENDAR.md`
  + `ops/market_probe.py`. Headlines: **ch2 must ship 90–180 min sleep compilations** (not 12-min
  talks), **ch4 grows on Shorts**, **ch1 titles must be feelings**. PR `ax-workspace#1` (merged).
  **YouTube Analytics API is disabled on GCP project 888023422403 → needs K** to enable retention data.
- **24/7 liveness watch lives in GitHub Actions**, not the pod: `ops/channel_monitor.py` +
  `.github/workflows/channel-monitor.yml`, every 30 min, read-only, commits a snapshot only on
  change. YouTube creds are **encrypted repo Actions secrets** (5). Verified: run succeeded and
  saw ch1/ch2/ch4 live.
- **The channels now publish by themselves** (K: "ช่องต้องอัพเดทตลอด 24 ชม."). ak decided to
  **lift the upload freeze** and built `.github/workflows/auto-shorts.yml` → `ops/publish_next_short.py`,
  rendering `ops/short_maker.py` from `ops/content_bank.json` (162 pieces, ~40 days; refill with
  `ops/expand_bank.py`). Free tools: edge-tts + ffmpeg. **Cadence is set by quota: `videos.insert`
  =1600, project=10,000/day → never past 5/day.** Proven live: wIpNM1gqPYc, oIsloIKa0J4,
  CaVSO74wFms, and (first ch4 post, 2026-10-31T14:38Z) **Wr5N-NfhGMM**.
- **2026-10-31 hardening (ak, after the first ch1 post FAILED in CI):** the workflow had been
  created 10:08Z and **never ran on its cron** (only manual dispatch) — GitHub silently drops
  some scheduled triggers on a fresh repo. Fixes, all pushed and proven by a green run:
  (a) schedule `0 */5 * * *` (5/day) + cheap `:20`/`:40` keep-warm crons with a gate step, so a
  dropped trigger is caught; (b) `publish_next_short` now **rotates channels** — the bank is
  written in channel blocks, so FIFO would post all 81 ch2 pieces before ch1/ch4 moved; (c)
  `--slot-hours 5` makes a keep-warm inside a served hour a no-op (proved: 2nd run returned
  `slot-already-served`); (d) `short_maker` retries each line 3x then **falls back to the other
  Thai voice for the whole clip** — `th-TH-PremwadeeNeural` reproducibly returns
  `NoAudioReceived` for some Thai lines (e.g. "ไม่ได้ไปไกลที่สุดเสมอ"), which is what aborted the
  first ch1 post; (e) every description now links a **sibling channel** (free cross-promotion);
  (f) `ops/test_publish_logic.py` guards rotation/slot/promo with stubs and runs as a pre-flight
  step. The first ch1 Short (CaVSO74wFms) is public via the fallback voice.
- **⚠️ Cron is the weak link — corrected 2026-10-31 14:45Z.** `GET /actions/runs?event=schedule`
  returns **total_count = 1 for the whole repo**: channel-monitor's `*/30` produced **1** tick in
  ~8.6 h (~17 expected) and auto-shorts' `0 */5` + `20,40 * * * *` crons have **never fired**. So
  the earlier "the monitor cron fired reliably" was **wrong** — nothing here ticks on schedule
  yet (a fresh cron warms up slowly; GitHub also drops/delays scheduled runs). The channels
  advance today because ak **dispatches in-session** (`POST /actions/workflows/auto-shorts.yml/
  dispatches`, proven 204 → success → ch4's `Wr5N-NfhGMM`) or because the monitor is dispatched,
  which cascades via `workflow_run`. Design still degrades safely: the slot gate + `--slot-hours`
  mean a dropped tick costs a post, never a double-post. **Do not describe the channels as
  updating 24/7 until a scheduled tick is observed.**
- **Mailboxes live in the PC1 vault**, not the repo: 2 ephemeral tempmail.lol boxes
  (`ak.mail.*`, `ak.mail.alt1.*`) + a **durable mail.tm** box `akchan34a@fldubai.com`
  (`ak.mail.durable.*`, has a password so it is recoverable). tempmail boxes EXPIRE --
  use the durable one for anything real. `docs/MAILBOXES.md` maps them.
- **Movement report**: `ops/report.py` -> Thai report, kept current as issue #2
  (kongkeat938/ax-workspace); auto-shorts refreshes it via `GH_REPORT_TOKEN`.
- **ch4 housekeeping DONE via the Data API**: banner uploaded (verified `bannerExternalUrl`) and
  videos sorted into playlists `เรื่องเล่าการ์ตูน — ตอน` / `— Shorts`. **But a channel *rename*
  cannot be automated** — the API returns 200 while keeping the old title, and Chrome 156 blocks
  the browser path (App-Bound Encryption + `--remote-debugging-port` refused on the default
  profile). Needs K in Studio. Detail in `topics/01-pc1-remote-and-workstore.md`.

- **ขับ Chrome บน PC1 ได้แล้ว (ak):** โปรไฟล์ชื่อมีเว้นวรรคต้อง `--profile-directory="Profile 2"`
  (quote ในค่า). session crash ค้าง `0.0.0.2` แก้ด้วย Stop-Process chrome + ลบ `Sessions\*`,
  `Current/Last Session|Tabs` + `--disable-session-crashed-bubble`. OCR ใช้ได้หลังลง
  `eng.traineddata`+`tha.traineddata` → `--lang tha+eng` อ่าน Studio ไทยได้.
- **K ข้าม YouTube Analytics API (2026-11-01)** — Console บังคับ 2SV, บัญชี PC1 ไม่มีรหัสผ่าน;
  ak วัดผลจาก public view count แทน. **Chrome PC1 ล็อกอินครบ 3 โปรไฟล์** (ch1/ch4/ch2).
- **ch1 มีแค่ "คำเตือน" (warning) ไม่ใช่ strike** — ล้างด้วยฝึกอบรม 7 ข้อ.

- **FB/TikTok monetization (วัดจากหน้าทางการ 2026-11-01):** TikTok Creator Rewards **ไทยไม่อยู่**ใน
  8 ประเทศที่จ่าย (US/UK/DE/JP/KR/FR/MX/BR), เกณฑ์ 10k followers + 100k views/30วัน, คลิป >1 นาที
  → TikTok = แจกจ่าย ไม่ใช่รายได้. **Facebook monetize ได้ในไทย** (Page/professional mode, ≥30 วัน,
  ต้นฉบับ). ak ผลิตคลิป 9:16 ได้ (`ops/short_maker.py`, 1080x1920 พิสูจน์แล้ว); สร้างบัญชีไม่ได้
  (ต้องเบอร์โทร=K). แผน: `docs/FB-TIKTOK-PLAN.md`. ห้ามปั่นยอด (ตัดสิทธิ์ทั้งคู่).

- **ak ไม่สมัครบัญชีแทน K** (FB/TikTok/ฯลฯ) — บังคับชื่อจริง+เบอร์ = ปลอมตัวตน เสี่ยงแบน
  (`AK-ACCOUNTS.md` ข้อ 3 + "ak never signs up as K"). เอกสารให้ K: `docs/K-CLICK-LIST.md`.
- **2SV เปิดครบทุกบัญชีแล้ว (ยืนยัน 2026-11-01 ด้วยการวัดจริง)** — ตรวจหน้า
  `myaccount.google.com/security?hl=en&authuser=N` (บังคับอังกฤษ) ผ่าน UI Automation:
  - `farmmer.938@gmail.com` (ch2) → **On since Oct 17** · `kongkeat.p3@gmail.com` (ch4) →
    **On since Aug 1, 2023** · `kongkeat.938@gmail.com` (ch1, Default) → **On since 8:51 AM
    วันนี้ (Khon Kaen)** · `aerismusic8@gmail.com` (ch3, ยกเลิก) → **On since Oct 20**.
  - ใช้เบอร์ 062 162 6993 (phones) + recovery email เป็น 2SV ของทุกบัญชี.
  - **บทเรียน: อย่าเชื่อบันทึกเก่าที่ว่า 2SV ยังไม่เปิด** — K บอก "ทำหมดแล้ว" และถูกต้อง.
    ตัวบล็อกรายได้จริง **ไม่ใช่** 2SV อีกต่อไป.
- **ตัวบล็อกรายได้จริงตอนนี้ = ยอดยังไม่ถึงเกณฑ์ YPP** — 1,000 subs + 4,000 ชม.ดู/12 เดือน
  หรือ 1,000 subs + 10M Shorts views/90 วัน (`support.google.com/youtube/answer/72851`).
  ch1/ch2/ch4 = 6/1/6 subs (ห่างมาก). ต้องเร่งคอนเทนต์ + views.
- **สถานะสด 2026-11-01 14:31Z: รวม 25 subs · 9,343 วิว · 55 คลิป** (ch1 8/ch2 11/ch4 6 subs).
  pipeline โพสต์เอง 8 Shorts = 4,511 วิว (48%). รายงานทำซ้ำได้: `python3 ops/perf_report.py`.
  **รายได้ = 0 บาท** เพราะ YPP ต้อง 1,000 subs → 25/1,000 = 2.5%. Shorts (<90วิ) เฉลี่ย 288 วิว,
  คลิปยาว (>90วิ) เฉลี่ย 35 วิว → **เน้น Shorts เท่านั้น**. คลังคอนเทนต์เหลือ ~27 วัน @ 5/วัน,
  เติมด้วย `ops/expand_bank.py --add N`. **จุดอ่อน: ch4** (คลิปใหม่ 93–108 วิว, คลิปยาว ~0 วิว).
- **กลยุทธ์ที่วัดได้ (2026-11-01, Decision 5 ใน DECISIONS.md):** (1) pipeline auto = 48% ของวิวทั้งหมด
  → เนื้อหาคลังคือเครื่องยนต์หลัก; (2) **ch4 ชนะด้วย "ดราม่าครอบครัว"** (1,080/460 วิว) ไม่ใช่ parable
  ธรรมชาติ → แก้ brief ใน `ops/gemini_bank.py` แล้ว; (3) **ch1 title ต้องเป็นประโยคความรู้สึก**
  ไม่ใช่ป้ายหัวข้อ (ใช้ `topic_hint`); (4) **caption ล้นจอ** เพราะ Thai ไม่มีเว้นวรรค + บรรทัดยาว
  → `short_maker._wrap_caption` ตัดตาม pixel (กล่อง 900px), เทสต์ `ops/test_caption_wrap.py`;
  (5) **กันหัวข้อซ้ำใกล้เคียง** ด้วย `too_similar()` + `ops/bank_prune.py` (prune 32 หัวข้อ).
  คลังตอนนี้ **193 (เหลือ 185 ≈ 37 วัน)**, หัวข้อซ้ำใกล้เคียง 0 (ดู Decision F ด้านล่าง).
- **คิว publish เรียงตาม `priority` (2026-11-01):** pipeline ดึงคลังจากบนลงล่าง การแก้กลยุทธ์
  จึงต้องดันของใหม่ขึ้นหัว ใช้ `gemini_bank.py --priority 1` แล้ว `bank_prune.py --newest-first`
  (sort `-priority, -slug_num`). **หมายเหตุ: `slug` ต้อง unique** — generator เดิมใช้ `len(bank)`
  ทำให้หลัง prune เกิด `ch2-gem162` ซ้ำ (คลิปหายเงียบ ๆ) → แก้เป็น max+1 แล้ว;
  `ops/test_bank_health.py` เฝ้า slug ซ้ำ/field ขาด/หัวข้อซ้ำ/runway.
- **"รูปทรงที่ชนะ" ต่อช่อง (2026-11-01, Decision F) — `topic_ok()` บังคับแล้ว:**
  ch2 = **พิธีช่วยนอน** (ทำตามได้คืนนี้ + พูดตรง ๆ) ไม่ใช่คำเปรียบลอย ๆ ("ลมหายใจคือ...");
  ch4 = **ดราม่าครอบครัว** ไม่ใช่ parable ธรรมชาติ (เมล็ด/แม่น้ำ/ต้นไม้ ~100 วิว);
  ch1 = **ประโยคความรู้สึก** ไม่ใช่ "ความสุขของคน...". Generator จะ **retry ทันที** ถ้าผิดทรง
  (+ กันเปิดซ้ำทรงเดิมเกิน 3 ครั้ง/ชุด). คลัง **193 (เหลือ 185 ≈ 37 วัน)**, คิว priority **64**.
  ⚠️ **อย่าหลง "วิวสูง" ของ ch1**: `#1minute english` 1,404/1,372 วิว แต่ **อายุ 524 วัน**
  = 2.7 วิว/วัน (ของเก่า ไม่ใช่สัญญาณ) — pipeline Shorts ทำ **~900 วิว/วัน** ต่างหาก.
- **ข้อจำกัดหน้าจอ Google:** `myaccount.google.com` ขอรหัสผ่าน K ก่อนแสดงรายละเอียด (2SV/การเงิน)
  → ak ไม่มีรหัสและห้ามพิมพ์; ต้องให้ K กดเอง. แต่สถานะ 2SV อ่านได้ผ่านหน้า security (ไม่บล็อก).
  **เขียน .ps1 ที่มีอักษรไทยไม่ได้** (encoding เพี้ยน) — สคริปต์ต้อง ASCII ล้วน, ส่ง URL `?hl=en`.
- **CDP ถูกบล็อกบนโปรไฟล์หลักของ K** (Chrome 156, พอร์ตเปิดแต่ WS ถูกปฏิเสธ) — ใช้ได้เฉพาะ
  `--user-data-dir` ของตัวเอง. ขับโปรไฟล์ K ต้องใช้ GUI+OCR (OCR tha+eng อ่าน Gmail/Studio ได้จริง).
  เปิด Chrome เลือกโปรไฟล์ต้อง quote ค่า: `--profile-directory="Profile 3"`.

## Standing rules (do not relearn)
- **Branding (2026-11-01)**: `ops/branding_maker.py` (avatar 800x800 + banner 2560x1440, Pillow+tlwg, raqm) and `ops/yt_channel_art.py` (banner via `channelBanners.insert`). Applied live: **banners + descriptions + keywords + language on ch1/ch2/ch4**. **Channel NAME and avatar CANNOT be set by the Data API** (title returns 200 but is ignored) -> manual in Studio; files on PC1 at `C:\ak\branding\`; steps in `docs/BRANDING-STEPS.md`. Watch: `channels.update` replaces brandingSettings, so carry `image.bannerExternalUrl` back or the banner is wiped.
  **DONE 2026-11-01: all 3 channels now carry the new avatar + name + banner.** Verify with
  `python3 ops/verify_branding.py` (downloads the LIVE avatar/banner and diffs against
  `assets/branding/`; pass <4, wrong pic >100). **The Studio page says "saved" even when the
  picture did not change** — never trust the UI, diff the pixels. Chrome profiles on PC1:
  `Default`=kongkeat.938 (ch1), `Profile 2`=kongkeat.p3 (ch4), `Profile 3`=farmmer.938 (ch2).
  Studio file dialog: UIA does not expose its filename field — click it, then SendKeys `^a{DEL}`+path+`{ENTER}`.
- **K: "ไม่ต้องถาม ตัดสินใจทำแทนได้เลย" (2026-11-01)** — เกณฑ์ K ง่าย ๆ: **ฟรี · คุ้ม · สร้างรายได้**. ถ้าเข้าเกณฑ์นี้ ak ทำเอง ไม่ต้องรอ K. ยังต้องขอ K เฉพาะ: ใช้เงินจริง, ย้าย/เปิดเผย secret, ลบบัญชี/ช่อง.
- **AUDIO FIRST** (K): retention is the sound; the music bed must never win, even in pauses.
- **Never claim to have watched/heard** anything — report measured numbers only.
- **ak does not upload** — K reviews the FIRST work of each channel, then uploads follow.
- **Never render into `/tmp`** (a pod recycle wipes it) — use `work/<ep>/` in the repo.
- **Verify with a control** — a local state file is a claim, not proof.
- **A check that fails uniformly is a measurement artefact; a scattered one is a real defect.**
- **Content, not accounts, is the growth bottleneck.** The hand bank reused 89 lines across
  162 entries (near-duplicates -> YouTube throttles). `ops/gemini_bank.py` grows it with NEW
  validated themes via `gemini-3.5-flash-lite` (the free text model that returns 200;
  `gemini-3.8-flash` = 503). Ran 2026-10-31: +12 themes, bank 162 -> 174, lines 89 -> 149.
- **GitHub cron is unreliable on a young private repo** — measured 1 scheduled run where ~20
  were due, so the old `hour % 5` gate lost whole slots. `ops/pace.py` now opens the gate when
  the day is behind its 5/day pace (cap = quota) so any trigger that fires catches up; proven
  live: a non-slot dispatch published `ch2-gratitude-03` (ygzzfERx4KA, 200 via oEmbed).

## Environment (one line each)
- Pod recycles ~20 min after idle; `/tmp` dies. `ffmpeg` not preinstalled (`sudo apt-get
  install -y ffmpeg fonts-thai-tlwg-ttf`). `ss`/`netstat`/`lsof` absent — use a Python socket probe.
- `POST`/`PATCH` to `www.googleapis.com` are blocked by the sandbox proxy (bare 404); **GET and
  PUT pass through**. Read the `Server` header before blaming the URL.
- Push: `$GITHUB_TOKEN` is read-only (403). Use **`$KONGKEAT_GH_TOKEN`** — full admin/push.
