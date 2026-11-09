# ARCHIVE — the full MEMORY.md index as of 2026-11-09 (75 KB)

Superseded by the compact `.openhands/memory/MEMORY.md` (the loader truncates a large
index, so the tail was being lost). Kept for the full detail of 2026-10-31 → 2026-11-08.

---

# Project Memory — ak (ai-content-lab)

## 🟠 2026-11-09 — the TRACKING system was lying (3 real defects, all fixed)
Follow-on to the 01:42Z foreman recovery. Rails were green; the *watching* was not.
1. **Learning loop blind on a spent Data API quota.** `studio_ai.py` + `video_review.py`
   read Analytics (own quota, works) but fetch titles from Data API `videos.list`, which
   **403s most days** → fell back to literal `"(title unavailable)"`. Measured 01:12Z run:
   **every winner on all 3 channels** was untitled, so the panel judged a channel it could
   not see and returned generic filler ("3 ข้อห้าม...", "เคล็ดลับลับ...") that
   `gen_short_scripts.py` then made into content. **Fix:** titles resolve from the committed
   manifests (`content/<ch>_shorts.json` + `_publish.json`); live title still wins. Pure
   `fill_titles()`. Guard `scripts/test_learning_titles.py` (74/104/49 videos keep titles).
2. **Health alert cried wolf.** `health.EXPECTED["foreman"]=90 min` but the chain ticks the
   foreman **every 2 h** → tripped on every healthy link; `set-thumbnails` 90 min vs the
   foreman's own **180-min** gate → unsatisfiable. **11 issues (#7–#18) opened+closed in 2
   days, all false.** **Fix:** thresholds vs the REAL driver: foreman 240, set-thumbnails 240.
3. **6 foreman-driven rails were invisible to health** (`studio-ai`, `selftest`,
   `counter-ledger`, `ch2-playlists`, `fetch music`, `short doors`). One was already dead:
   **`fetch music` failing for a day** (`ModuleNotFoundError: numpy` — validator imports
   `test_music_beds.py`; workflow installed ffmpeg but not `requirements.txt`). **Fix:** the
   workflow installs deps; the 6 rails are in `health.EXPECTED`; the runs lookup is by
   **numeric workflow id** (a display name ≠ file name, e.g. `"fetch music"` vs
   `fetch-music.yml`, 404'd and blanked the report via `_error`).
- **Guards** in `scripts/test_watchdog.py`: (a) every health threshold must exceed the real
  driver cadence, (b) every foreman-dispatched rail must be watched (condition-gated ones —
  `remake shorts`, `apply-packaging`, `remove-bad-cut`, `watchdog` — exempt). Both verified
  to FAIL on revert. **Rule: a rail the foreman drives but health ignores can fail silently.**
- **Measured win:** watch-hours 28d **79.12 → 219.87 h** (genx 120.2, dharma 79.8, kongkeat
  19.9; views 27k/14k/6.1k). `docs/PROGRESS.md` + issue #6 refreshed. Detail:
  `docs/STATUS-2026-11-09.md`, `.openhands/memory/2026-11-09.md`.

## 🔴 2026-11-09 — foreman was DOWN ~6 h (committed git conflict)
`content/upload_log.json` on main held raw conflict markers from a
`git pull --rebase --autostash` in `publish_shorts.commit()`. Every foreman run
19:35Z→01:36Z died on `JSONDecodeError`, so **no rail was driven from the chain**
for ~6 h (schedule-driven rails still ran). Fixed: union the ledger (append-only),
plain `--rebase` (no autostash), `_union_resolve_upload_log()`, and a new
**`scripts/test_repo_hygiene.py`** (in `selftest.yml`) that fails on any line-start
conflict marker or unparsable JSON. Foreman verified live → 3 dispatches, all
success. Detail: `.openhands/memory/2026-11-09.md`. **Rule: any file two workflows
commit concurrently needs a writer-side conflict guard.**

**Agent name: `ak`** (renamed from AX by K, 2026-10-31). Owner **K**; Thai answers, measured
evidence. This file is an **index** and must stay small — the loader injects it every session
and **truncates the tail**, which is why the old 48 KB file lost its newest work. Detail lives
in `topics/*.md` and the daily logs.

## 🎨 2026-11-08 — Packaging rail shipped for ch2 (the meeting plan, executed)
Competitor research found the search blocker is **packaging, not reach**: no Farmmer
video in the top 30 for ธรรมะก่อนนอน, while 4.3k-sub channels hold 600k views.
- **`scripts/make_cover_youtube.py`** (NEW) — 1280x720 cover in the winning recipe:
  glowing gold Buddha + deep-navy night + big heavy-stroke Thai text. `_gild()` =
  `autocontrast` then composite gold by luminance → museum bronze reads as glowing
  gold AND the set shares one warm grade. `variant` alternates text side (mirrors
  the statue) so a channel page isn't a wall of identical covers. Vision 7/10 → 8/10.
  Art = 8 CC0/PD Commons statues in `assets/branding/farmmer/art/` (+credits.json).
  ⚠️ Commons `generator=search` 429s after ~5 queries from this pod.
- **`content/ch2_packaging.json`** + **`scripts/apply_packaging.py`** +
  `apply-packaging.yml` (08:25/09:25 UTC + push) — title+tags+cover via Data API,
  ledger `content/packaging_changes.json`, quota-deferral safe. Covers all 13 ch2 vids.
- **Playlists**: `channel_overhaul.py` ch2 PLAN gained ปล่อยวาง/คลายกังวล + นิทาน;
  new `ch2-playlists.yml` (08:40 UTC). `organise()` is idempotent.
- **Hook rail already existed** (`--hook-file content/hooks/dharma.md`, used by
  night-compilation.yml). Only trimmed to ~44s + dropped its false "ยี่สิบนาที" claim.
- **`publish_batch.py --publish-at ISO`** — YouTube holds private and flips at
  publishAt, so a dropped cron can't miss a slot (needs privacyStatus private).
- **Live apply DEFERRED** — Data API quota was already spent (403 quotaExceeded).
  CI proved auth+wiring by deferring cleanly. First writes at the 08:25 UTC tick.
- ⚠️ **`scripts/test_watchdog.py` fails any workflow that has a `schedule:` but is
  not dispatched by `foreman.py`** (GitHub cron is unreliable here). New rails MUST
  get a foreman rule. Added rules for apply-packaging / ch2-playlists / remove-bad-cut.
- ⚠️ **First-run CI bugs that only appear when you actually dispatch:** `git add
  <new-file>` aborts the step with `fatal: pathspec ... did not match` when the
  ledger does not exist yet (use `git add -A content/`); and re-rendering covers in
  CI uses a different Pillow than the build, so upload the committed JPG instead.
- **Bad cut `HkbSguA53ro` STILL LIVE** — delete defers on the spent quota; now
  data-driven via `content/deletes.json` + a `.done` marker, foreman-driven.
  Doc: `docs/PACKAGING-PLAN-2026-11-08.md`. ⚠️ MEMORY.md is ~71 KB — over the
  loader's injectable size; prune when convenient.

## 📬 2026-11-08 — อ่าน Gmail จากพอดได้แล้ว (ไม่ต้องพึ่ง PC1)
K: "รหัสเมล์ที่สร้าง secret ไว้ เอามากรอดเมล์เลย" ⇒ **ทำได้จริง end-to-end**.
- รหัสใน secret `IMAP_ACCOUNTS` = **รหัสผ่านจริงของ Gmail** (9 ตัว) ใช้ล็อกอิน Google ได้
- GitHub secret เป็น **write-only** ⇒ ย้ายออกมา**เข้ารหัส RSA** ด้วย
  `scripts/fetch_secret.py` + `.github/workflows/cred-transport.yml` (ciphertext อยู่ใน log
  สาธารณะได้ — กุญแจถอดอยู่พอด `~/.pod-cred-key.pem` เท่านั้น)
- ล็อกอินคำสั่งเดียว: `python3 scripts/pod_mail_login.py --user kongkeat.938@gmail.com --from-secret --store`
  - `Chrome.real_click` (เมาส์จริง) เพราะ Google ไม่รับ JS .click บนหน้า 2FA
  - ไป `continue=apppasswords` ตรงๆ ⇒ K **แตะมือถือครั้งเดียว** (navigate ซ้ำ = ขอ 2FA ซ้ำ)
- **ผล:** App Password 16 ตัว → secret `IMAP_ACCOUNTS` (2026-11-08T08:48Z). **พิสูจน์:** INBOX 824
  ฉบับ, UNSEEN 683, `mail_watch --imap-only` PASS. Detail: `2026-11-08.md`
- ⚠️ หลังพอดล้างต้อง `pip install cryptography` ก่อน (หายทุกครั้ง)

## ⭐ 2026-11-08 — AVD fix shipped: the long-form was ONE card looping (live 3HCOe1jZj2c)
- **Root cause (measured):** the dharma 120-min file's `averageViewDuration` = **379 s = 5.2%**.
  `make_night_video.py` looped **one static cover card** for the whole file → screen never
  changed → YouTube reads it as low-effort/reused content. It is the format, not the audio.
- **Panel (4 camps, `docs/PANEL-2026-11-07c.md`):** gemini-3.5-flash-lite, gemini-3.6-flash,
  gemma-4-31b-it, gpt-oss-20b (DeepSeek/Zhipu down). Verdict, by ROI: (1) spoken **hook**
  first ~20 s, (2) cut to **20–30 min**, (3) **change the picture per chapter**, (4) do NOT
  pump 8–10 h loops (Reused Content trap at YPP review). "คนอยู่ 4–6 นาทีเท่าเดิม" ไม่ว่า
  คลิปจะยาวแค่ไหน → ความยาวสั้นลงทำให้ %AVD ดีขึ้นทันที.
- **Shipped:** `scripts/make_chapter_video.py` (NEW) = one Ken Burns card per piece, chapter
  label, crossfade; `make_compilation --hook`; `build_night --chapters/--hook`; wired into
  **all three rails** (genx, ch4, dharma). Card cap `MAX_CARDS=30` coalesces pieces on a long
  file (120 min → ~26 cards ≈ 8 min/ใบ) so the xfade chain stays bounded. Test:
  `scripts/test_chapter_video.py` (one card per piece, consecutive cards differ in luma, tv
  range, TP ≤ -2.9). Fingerprints of all rails fold in `make_chapter_video.py`.
- **Proof (CI run 42431978059 SUCCESS):** hook 11 s + 8 pieces ×2 = **17 cards**, 26.3 min,
  **-14.4 LUFS / true peak -3.2 dBFS**, verdict pass → **live https://youtu.be/3HCOe1jZj2c**
  (ตาต้า GenX, public, manifest key `ch1_auto_202645`). Report `docs/STATUS-2026-11-08-avd.md`.
- **Not yet measured:** whether AVD actually lifts. Do NOT claim a win before the 26-min
  file's AVD has a week of data. Baseline to beat = **5.2%**.
- **Lesson:** ฟอร์แมตเดียวที่ทำให้ภาพนิ่ง = ตัวฆ่า AVD; เปลี่ยนภาพตามบท (ทุก 3–5 นาที) คือของถูก
  ที่ได้ผล ส่วนการเคลื่อนไหวความละเอียดสูงหลาย layer ชนเพดานเวลาเรนเดอร์ CI.

## ⭐ 2026-11-07 — genx long-form rail: the channel had Shorts reach and zero destination
- **Advisor panel closed (3 camps, satisfies ≥3-distinct-camps rule):** Google ×3 models
  (`gemini-3.5-flash-lite`/`3.6-flash`/`gemma-4-31b-it`), **OpenAI-OSS** (gpt-oss-20b via
  Pollinations text), **OpenHands default agent** (DeepSeek via OH Cloud). Verdict + dissent:
  `docs/PANEL-2026-11-07-CONSENSUS.md`. All 3 agreed: **genx is the biggest gap** — 52 Shorts
  and the highest Shorts reach (14,566 views, +78 subs/28d) but **ZERO long-form**, so every
  genx Short funneled to an **empty playlist** `PLXEV3B3DcgsU`. Shorts reach never counts
  toward YPP watch-hours. Panel split on length (Google 120min+, OSS 10-15min, DeepSeek
  20-40min+"fix AVD 4% first"); **ak's call: start at 30 min** (the length ch4 proved) as the
  AVD measurement that decides the next length.
- **Built the genx rail** (mirror of the proven dharma/ch4 rail): `scripts/gen_philosophy_scripts.py`
  (GenX "permission" arc, Thai-only/no-digit gates), `genx-longform.yml` (30-min build, Tue
  04:47 UTC), `publish-ch1.yml` (Data API upload, `YT_CH1_REFRESH_TOKEN`), `content/ch1_publish.json`,
  a `genx` channel in `add_release_to_manifest.py`, and `foreman.py` feeds it weekly.
- **🔑 The funnel fix:** `add_release_to_manifest.py` now writes the channel's **playlist id into
  every manifest entry** (config `"playlist"`), so `publish_batch.py` inserts each uploaded
  long-form into the exact playlist the Shorts point at. Writing the entry is not enough —
  the playlist insert is what closes the funnel.
- **Proven E2E in the pod:** `content/ch1_long_01` (10 pieces, 305 lines) → 970.9s video →
  `verify_night.py` **verdict pass**: -14.6 LUFS, true peak -3.1 dBFS, 1920x1080 color_range=tv,
  bed headroom 20.6 dB. Commit `3c23289`.
- **OH Cloud advisor gotcha:** leave `llm_model` at default (DeepSeek answers). Setting
  `openhands/claude-sonnet-4-5` or `openhands/gpt-5` → APIError "model not available" for this
  key. OH Cloud is slow (~10-15 min/answer); read `llm_message.content` from `events/search`.
- **Pod render works:** `sudo apt-get install -y ffmpeg fonts-tlwg-*` + `pip install edge-tts
  Pillow numpy`; edge-tts reaches the network. `verify_night.py` takes a **positional** path,
  not `--video`.
- **genx long-form is LIVE: https://youtu.be/l5hkDGVIYXE** (32.4 min, public, CI-built).
- **⚠️ Funnel leak found + fixed:** a playlist insert that hits the shared quota 403 at upload
  time left the video live but **out of the playlist**, and `state=published` meant it was never
  retried → the funnel stayed dead. `publish_batch.py` now records `playlist_added` and runs a
  **repair pass** each tick; `foreman.py` dispatches `publish-ch1` while a repair is pending
  (GitHub's `schedule` never fires here). Verify `playlist_added: true` after the 08:00 UTC
  quota reset.

## ⭐ 2026-11-06 — Long-form rail is now a closed autopilot (release→manifest→publish)
- The night rail built a verified 120-min compilation, put it on a Release, and **stopped**:
  nothing wrote the manifest entry `content/ch2_publish.json`, so a person had to. That gap
  was the real bottleneck (not the build). Fixed by `scripts/add_release_to_manifest.py`
  (idempotent) + `night-compilation.yml` running it after the release and **dispatching
  `publish-batch.yml` explicitly**. Advisor panel 2/3 camps agreed (gemini-3.5, gpt-oss-20b).
- **⛔ A push made with the default `GITHUB_TOKEN` does NOT start another workflow**
  (anti-recursion). Rely on a push trigger and it silently does nothing → dispatch explicitly
  (`gh workflow run`, job needs `actions: write`).
- **✅ `KONGKEAT_GH_TOKEN` CAN dispatch workflows from the pod** (the plain `GITHUB_TOKEN`
  cannot → 403 "Resource not accessible by integration"). Use it for `gh workflow run`.
- **Proven E2E 2026-11-06:** `night_01` → 124-min file → release → manifest `night_sleep_01`
  → publish → **live** https://youtu.be/ZrjMi0pcDYo. **Farmmer long-form now 5.**
  Flow + numbers: `docs/LONGFORM-AUTOPILOT-2026-11-06.md`.
- **ch4 rail had the same leak AND a fixed release tag** (a rebuild clobbered the release).
  Fixed the same way; `add_release_to_manifest.py` is per-channel now (`--channel`). Proven:
  `ch4_family_long_02` → https://youtu.be/BnUOckow0-Q (public).
- **ch4 rail now feeds itself** (K: "ทำให้ครบ" → "ก ทำไปเลย"). New
  `scripts/gen_family_scripts.py` = ch4's twin of `gen_night_scripts.py`: 12-beat family arc,
  warm first-person "ผม" memory (matches the ch4 voice). `ch4-longform.yml` mints its own
  ISO-week set on schedule (Thu 03:37 UTC) + commits it, title follows the week's theme;
  foreman dispatches it weekly with `generate=true`. **Proven E2E:** generated set
  `ch4_auto_202645` → 33.4-min build → live https://youtu.be/6Vs7vTUTMN0 (**ch4 long-form now 3**).
- **🖼️ K: "ภาพห้ามซ้ำ ทุกคลิป gen ภาพใหม่"** (2026-11-06). Root cause: `build_night.py`
  used ONE default image for every build and thumbnails drew the video's own frame →
  repeats (proof: `k_tone_01` = `night_sleep_01` byte-identical). Fix = new
  `scripts/gen_cover_image.py`: **Pollinations → Wikimedia → procedural PIL** (never fails);
  strips the `pollinations.ai` watermark (crop bottom 6%); 2 styles dharma/family.
  `build_night.py` now mints a per-set cover; `make_video_thumbnail.py --gen-art` draws a
  unique image per video (seeded by id); polish-all uses `--gen-art --limit 25`.
  **K's rule for text: AI draws ONLY pattern/scene, WE draw the Thai text** with our fonts —
  AI-written text is always garbled (vision-verified). Gemini image API still 429 quota 0.
- **⛔ BIGGEST FINDING:** `polish-all` + `watch-hours` were **NOT in `foreman.py`'s plan**, so
  they relied on GitHub's `schedule` — which has **never fired for this repo**. The "change
  every title/thumbnail" job would have stalled at 94/221 titles + 0 thumbnails forever. foreman
  now dispatches polish-all daily 08-12 UTC (post quota-reset) + watch-hours weekly, and the
  night dispatch passes `generate=true` (without it the weekly run rebuilt an existing set and
  the fingerprint skip made it a **no-op that published nothing**).
- **Watch-hours measured (Analytics API, own quota — works when the Data API is spent):**
  28d total **79.1 h** (genx 24.2, dharma 39.4, kongkeat 15.5) vs **30.1 h on 2026-10-31 = ×2.6**.
  The 120-min `F4qFHoVpEyI` = **8.72 h / 146 views = 0.0597 h/view**, the top video on dharma
  (22% of its watch-hours alone). Auto-recorded weekly to `docs/watch_hours.json`.
  Detail: `docs/WATCH-HOURS-2026-11-06.md`.
- The scheduled run now also **generates its own weekly content set** (`gen_night_scripts.py`,
  ISO-week themed, reused within the week) and commits it before building.

## ⭐ 2026-11-06 — Long-form SEO pass done with the EXISTING token (no new consent)
- The `youtube.upload` scope the tokens already hold covers **title, description,
  tags, category** writes (`videos.update`) AND **thumbnails** (`thumbnails.set`).
  Only **comments/replies** need `youtube.force-ssl`. Verified by round-trip.
- **Applied to all 30 long-form videos:** titles rewritten (keyword-first),
  36 thumbnails designed from the video's own frame, and description+tags written
  (29 videos, ~230ch + 11-12 tags). Tools: `scripts/optimize_titles.py`,
  `make_video_thumbnail.py`, `optimize_seo.py`. Ledgers: `docs/{title,seo}_changes.json`,
  control `docs/views_snapshot.json`. Judge at 14 days.
- **Shorts titles were a wasted lever, measured:** views are **93-97% Shorts feed**,
  only **1.5-2.5% YouTube search** (`insightTrafficSourceType`). 10 of the first 11
  "changed" videos were Shorts → a title cannot move feed views. Do NOT spend effort
  on Short metadata; the testable surface is **long-form** (search is its path).
- **Thumbnail-detection gotcha:** `maxres` presence or an `sqp=` URL marker does NOT
  prove a custom thumbnail (an HD auto frame has maxres too). Only a **pixel compare**
  of live `i.ytimg.com/vi/<id>/maxresdefault.jpg` vs the generated file is reliable.
- `Pillow` is NOT in the pod by default — `pip install Pillow` before any poster/thumb script.
- Advisor panel scorecard: **gemini 100/100, pollinations 100/100 = KEEP** (fast, ~1-2 s);
  OpenHands advisors >10 min/probe = WATCH. `scripts/panel_scorecard.py`.

## ⭐ 2026-11-05 — Shorts watch-hours do NOT count toward YPP (measured)
Verified on the official page (support.google.com/youtube/answer/72851): "any qualified
watch hours from Shorts views in the **Shorts Feed** won't count towards the 4,000
qualified public watch hours threshold." **28-day split measured** (Analytics
`creatorContentType`): Shorts **30.3 h** vs long-form **2.9 h** → **91% of our watch
time is invisible to the only gate that pays.** The 4,000-h path is at 2.9 h (0.07%);
the 10 M Shorts-views/90-day path needs ~300× today's 354 views/day. **Neither is close.**
⇒ **The lever is long-form (and/or the alternative revenue in `docs/FAST-REVENUE-PLAN.md`),
not more Shorts.** Shorts stay as reach + subs only. Advisor (Gemini) agrees.
**Loop is the watch-time lever, measured:** genx `WA8g6zCiMmo` (25 s) avg% **347.8** →
6.7 watch-h from 925 views; kongkeat `udi7bekVJiA` avg% 103.6 → 8.1 h. But those hours
are Shorts-Feed → still don't count. Long-form live: `F4qFHoVpEyI` (2 h 47 m, 293 views),
`q6VXmPP57xY` (1 h 50 m, 4 views), `2PEjuEFpeY8` (17 m, 13 views).
**Quota is project-wide, not per channel** — a "Video Uploads per day" 429 stops all 3
channels at once (measured 2026-11-05 15:36Z, resets ~08:00 UTC). `publish_shorts.py`
now treats both `uploadLimitExceeded` and `Video Uploads per day` as an expected stop.
**Generator guard:** `gen_short_scripts.py valid()` now rejects any character outside
Thai/Latin/digits/punct — Gemini had leaked Hangul/Japanese/Telugu into 4 live
descriptions + 3 pool lines (all repaired 2026-11-05).

## 🔗 2026-11-05 — the Shorts→long-form funnel is now wired (the measured lever)
A Short is only worth the reach it *forwards*: its own watch time does not count toward
YPP. **45 Shorts had no destination at all** (genx 14, dharma 5, **kongkeat 26 = its
whole catalog**). `scripts/link_shorts.py` (+ `.github/workflows/link-shorts.yml`) appends
each channel's long-form playlist link, idempotent + additive; applied live → **45 linked,
0 failed**, re-run → 0 missing. **The long-form rail is undiscovered, not broken:**
`F4qFHoVpEyI` has 301 Data-API views but **2 Analytics views / 0 counted minutes** (both
from RELATED_VIDEO), and its Release MP4 is faststart-OK (`ftyp`+`moov` in the first 8 KB).
**ch4 has no on-niche long-form** — its only long-form is the classical-tale set (1-6
views); the family shape measured 460-1,083. So `content/ch4_family_01/` (10 warm family
pieces) + a dispatch-only `ch4-longform` workflow (builds in CI — **the pod has no ffmpeg /
PIL / edge-tts**) renders a 20-min file that **verified pass** (-14.5 LUFS / -3.2 dBTP /
1920x1080 tv) and lands on Release `ch4-family-long-01`. `publish-ch4` uploads it.
**Voice trap:** `th-TH-PremwadeeNeural` failed all 5 CI attempts ("No audio received");
use **`th-TH-NiwatNeural`** (6 ok/0 fail).
**Upload cap is two kinds:** ch1/ch2 = project-wide 429 ("Video Uploads per day"); ch4 =
per-channel 400 `uploadLimitExceeded`, clears at **08:00 UTC** (not 3 h). `publish_batch.py`
now defers cleanly when `content/upload_limit.json` says a channel is capped (no 132 MB
re-download). **GitHub's scheduler never fires here**, so `foreman.py` (run by the watchdog
chain) dispatches `link-shorts` every ≤6 h and `publish-ch4` once ch4's cap note has
cleared. Final funnel state: **0 Shorts missing a destination on all 3 channels.**

## 🏁 2026-11-03 — the business turn (ak runs it)
K's standing order: **ak runs this as its own business; revenue is the objective; all tools;
ask ChatGPT/Gemini on a first failure, never ask K.** K owns the accounts.
- **ch2 long-form is LIVE: `F4qFHoVpEyI`** (120 min) and **`2PEjuEFpeY8`**
  (K-tone, 17 min, public 2026-11-04 — K approved the tone and said to release).
  `night_110` held to 2026-11-05 20:00 Thai. **Publishing works while the read
  quota is spent** (`videos.insert` has its own bucket; the rail skips the
  `channels.list` check on a quota 403).
- **7 Shorts live** (`exm1OwwngzI 5QRxCDH1iQw CAIFSg_Edxg AANBJpLDpUc MiF0Bz4Z_NQ ODC1nNwp6Sg
  Luv3HBRgY48`); pool = 20 scripts, grows nightly via Gemini.
- **Rails (all CI, no browser):** `publish_batch.py`+`publish-batch.yml` (long),
  `make_short.py`+`publish_shorts.py`+`publish-shorts.yml` (Shorts),
  `gen_short_scripts.py`+`grow-shorts-pool.yml` (content), `set_thumbnails.py` (covers).
- **Rule learned:** never gate a write path on a read call's quota — `yt_auth.load_credentials`
  verifies the channel with `channels.list` (quota-limited) and exits when quota is spent,
  which killed publishing; take the token straight from the env instead. `videos.insert` has its
  own bucket and works while reads 403.
- **Rule learned:** an ephemeral runner loses an id that is only in its working tree — commit
  the ledger **inside** the script the moment an id returns, or a failed run re-uploads.
- **ch2 daily upload ceiling is real:** `uploadLimitExceeded` after ~7-8 uploads/day.
- Gemini text = `gemini-3.5-flash-lite` only (2.5/2.0-flash → 404). Plan: `docs/REVENUE-PLAN.md`.
- **GitHub `schedule` NOW FIRES here** — corrected 2026-11-04: `event=schedule`
  total_count = **6** and the ticks ran (`grow-shorts-pool` 01:59Z, `set-thumbnails`
  00:53Z, `publish-batch` 23:18Z). The earlier "total 0" was a new-repo cold start,
  not a permanent block. The watchdog→foreman chain is still the *reliable* path
  (it re-chains itself), but do not claim cron is dead. Kill switch `content/STOP`.
  Docs: `docs/MONITORING.md`.
- **Niche truth (measured 2026-11-03, ch2 dharma):** long-form winners = **บทสวดมนต์ก่อนนอน /
  ปล่อยวาง, 20 min–3 h** (21.4M, 21.0M, 12.4M views). Shorts winners = **53 s–1:33** with a
  **question** hook ("เหนื่อยใจอยู่ใช่ไหม"). Our Shorts were 19 s → changed to 8-9 lines + rate
  -15% = **46 s**. `scripts/consult.py` = ask Gemini with real numbers (K's order: ask an AI,
  never K).
- **ch2 upload ceiling ~7-8/day**; `thumbnails.set` 429s after ~3 → use `--skip-existing`.

## 📊 2026-11-04 (session 2) — status report + fast-revenue plan
- **Measured live:** genx **26** subs / 9,518 views · dharma **22** / 6,751 · kongkeat **7** /
  3,746. Total 55 subs, 20,015 views, **348 watch-h (upper bound)**. **Shorts = 98.4% of all
  views.** Docs: `docs/STATUS-2026-11-04.md`, `docs/FAST-REVENUE-PLAN.md`.
- **YPP 2026 (verified):** Tier 1 = **500 subs + 3,000 h (or 3M Shorts views/90 d)** → fan
  funding; Tier 2 = 1,000 subs + 4,000 h (or 10M Shorts). **Doubles 2027-02-01.** Thailand
  eligible. Shorts views and watch hours never combine.
- **Funnel repair (done):** 10 dharma Shorts shipped with no link to the 120-min video.
  `scripts/backfill_short_links.py` added it to the **6 sleep-hook Shorts**; the other 4 are
  story/quote clips (`ข้อคิดชีวิต`/`การ์ตูนครอบครัว`) where a sleep link is a mismatch — left
  alone. dharma funnel now 21/25.
- **Fixed 3 rail defects:** (a) `Mv0jl7KhxIE` (deleted dup) in `ch2_thumbnails.json` made
  `set-thumbnails` exit 1 every run → removed; (b) `health.py` read runs from one repo-wide
  `?per_page=60` page (filled by `pages build and deployment`) so slow rails read STALE →
  now reads each workflow's own runs endpoint; (c) `foreman.yml` died on a rebase conflict over
  the generated `docs/HEALTH.md` → push first, abort-and-skip on conflict.
- **`--only` must be wired into the selection loop**, not just the arg parser — first run of
  the backfill ignored it and touched all 10 (had to revert 4).

## 🏛️ Authority (2026-11-04, session 2) — ak decides everything
K's words: **"ak ต้องบริหารและตัดสินใจเองทุกอย่าง k กำหนดเป้าหมายให้เท่านั้น"** → ak holds
full operational authority; K sets goals only. **Do not bring operational choices back to K.**
Reversible, in-policy work (content, funnels, rails, cadence, promotion) = ak acts.
**2026-11-04 K closed all three open asks:** (1) analytics = "ak รีโมทไปทำเอง" — **done, and
nothing was needed** (see below); (2) PromptPay = **declined**; (3) FB/affiliate = **deferred**
("ยังไม่ถึงกำหนด"). ⇒ ak has **no open question for K**. Do not create new ones.

## 📊 REAL analytics (2026-11-04) — the old numbers were wrong
- **The YouTube Analytics API IS readable with the existing tokens.** Granted scope is
  `https://www.googleapis.com/auth/youtube`, which Analytics accepts. Verified on all 3
  channel tokens → `scripts/analytics.py` reads watch-hours, averageViewDuration/Percentage,
  subs gained/lost per video. **The stored belief "needs yt-analytics.readonly / K re-consent"
  was WRONG** — no re-consent was ever needed. (Impressions/CTR is not a valid v2 metric; use
  `insightTrafficSourceType` / the reporting API for that.)
- **Real watch time = 31 h/year across all 3 channels** (genx 10.2 · dharma 8.5 · kongkeat 12.3;
  28-day total 30.1 h). The **348 h** figure in earlier docs was a naive `duration × views`
  upper bound — **~11× too high**. **watch-h/view = 0.0015** (views are not watching).
- **THE LOOP LEVER (measured):** every video with `averageViewPercentage > 100%` holds the most
  watch time — `udi7bekVJiA` (kongkeat) 8.12 h @ 103.6%, `WA8g6zCiMmo` (genx) 6.70 h @ 353.7%,
  `g0eWYjCEYTc` 3.10 h @ 115.1%. avg% > 100% = the viewer re-watched/looped. kongkeat/genx give
  ~3× more watch-h per view than dharma (dharma has views but short watch). Build videos that
  **loop cleanly** (end cuts back to start, no hard outro) — that is the controllable lever.
- **API limits confirmed (2026-11-04):** `commentThreads` → 403 (needs `youtube.force-ssl`,
  which our tokens lack) ⇒ **pinned comments are impossible via API**; the feed funnel must
  be in the **description**. `impressions`/`impressionClickThroughRate` are not valid
  Analytics v2 metrics (400) ⇒ CTR is not directly readable.
- Distance to YPP (honest): 500 subs at 0.75/day ≈ 593 d; 3,000 h at 1.08 h/day ≈ 2,750 d;
  3M Shorts views/90d needs 112× the current rate. Nothing is close; watch-hour is the only
  route where 1 unit = 1 count.

## 🔗 Funnel decision (2026-11-04, session 2) — point at the PLAYLIST, not the video
- A single `youtu.be/<id>` link is fragile (delete the video → the link dies on every Short).
  The **playlist** (`PLBpZCGnd7Q5Y` "หลับลึกทั้งคืน — ฟังยาว") is durable and autoplays into
  the next long file → more watch-hours per tap. Decision: every dharma Short and every
  long-form description links the **playlist** (and the 120-min file). Applied live to the 21
  sleep Shorts + 2 long videos; `publish_shorts.py` writes it for all future Shorts.
- **`night_110` was a duplicate risk:** its description/title were near-identical to the live
  120-min file (`F4qFHoVpEyI`), and it is a *different* 684 MB render. Retitled + re-described
  as "ฉบับยาวพิเศษ" before it auto-publishes 2026-11-05 20:00 Thai.
- **Cross-promo:** `promote_channels.py --apply` wrote the sibling-channel block into 9 genx +
  8 dharma videos that lacked it (1 dharma skipped: description too long). ch4 (kongkeat) was
  already complete.
- **`publish-batch` uploads while the read quota is spent** (`videos.insert` has its own
  bucket; the rail skips the `channels.list` check on a 403) — so night_110 is not blocked.
- **`night-compilation` does NOT upload by itself** ("ak does not upload; K reviews the first
  work of each channel") — but K has approved ch2 long-form, so the rail is effectively open;
  treat the `publish: true` input as approved for ch2.

## ⚙️ Rail ops — measured 2026-11-05
- **Thumbnail gate = per-account, NOT "every channel" (corrected 2026-11-05).** Live
  `thumbnails.set` test: **ch1 + ch2 OK**, **ch4 (kongkeat.p3) → 403 "doesn't have
  permissions to upload and set custom video thumbnails."** So the old "thumbnail locked
  behind phone verification (ทุกช่อง)" was wrong — only ch4 needs K to verify. The path is
  **Studio → Settings → Channel → Feature eligibility → Intermediate → VERIFY PHONE
  NUMBER** (also `youtube.com/verify`); custom thumbnails is an *intermediate* feature.
  Detail: `.openhands/memory/2026-11-05.md`.
- **The watchdog chain's weak point is the link job itself.** A ~2 h `ubuntu-latest`
  job can be reaped mid-run (`"The hosted runner lost communication with the server."`),
  so the closing `dispatch("watchdog")` never fires and **the whole timer stops** until
  a human re-dispatches. Detect: latest `watchdog` run = `failure`/stale.
  Recover: `gh workflow run watchdog.yml -f cycles=2 -f interval=5400 -f chain=true`.
- **GitHub Actions logs are NOT readable here** — `/actions/runs/<id>/logs` yields a
  22-byte stub zip; `/jobs/<id>/logs` = 404. Read the failure via **check-run
  annotations**: `gh api repos/.../check-runs/<job_id>/annotations`.
- A `queued` run that never starts (e.g. account-watch `41809364136`) cannot be
  cancelled (409); ignore it.

## 🗂️ TOPIC FILES
- `topics/00-pipeline-and-channel-facts.md` — the 3 channels, registry, yt938-1, view data, image ceilings.
- `topics/01-pipeline-build-and-measure.md` — build/measure loop, ffmpeg, gates, review page.
- `topics/02-gates-and-traps.md` — stale-record traps, `imgutil` trap, recovery, pod-empty.
- `topics/03-pc1-and-storage.md` — PC1 drivability, D: migration, sandbox facts, user prefs.
- `ARCHIVE-full-MEMORY-2026-10-31.md` — the whole old file, verbatim.

## 🚨 READ FIRST — ak runs THREE channels; ch4 = kongkeat pratumma
- ch1 `@tatagenxgeny` `UCI6EfsgM1HNjrYarvigxyrQ` · ch2 `@farmmer-n9t` `UCM3QO5L_pmj34n1JVlbhh-w`
- ch3 `@aerismusicth` `UCm44BjAn03ruOF-WaA3ZRww` · **CANCELLED 2026-10-30** (handed to another AI)
- ch4 `@kongkeatpratumma` `UC7gCIu4G_7QCEJ8hJ-34zoQ` · account kongkeat.p3@gmail.com · token `YT_CH4_REFRESH_TOKEN`
- **`@aerisanime` is NOT ch4** — a different channel (263 anime edits, 10.5k subs). Verify with `channels?mine=true`.
- **This repo (story-video) is a different project from `ax-workspace`/yt938.** Canonical
  registry: `ops/ax_channels.json` in ax-workspace; `channels.json` here is generated.

## 📉 Where the effort is wasted — measured 2026-11-03 (answers K's "is the load too heavy?")
| ch | subs | vids | views | median last-10 | <50 views | posts/7d |
|---|---|---|---|---|---|---|
| ch1 genx | 12 | 38 | 3,494 | 18 | 6/10 | 10 |
| ch2 dharma/farmmer | 13 | 24 | 4,218 | **86** | 3/10 | 20 |
| ch3 aeris (cancelled) | 7 | 34 | 2,510 | **0** | **10/10** | 30 |
| ch4 story | 7 | 17 | 2,748 | **103** | 3/10 | 13 |
- **Channel count is not the quality problem** — ch4 (newest) has the best median. The waste is
  **ch3** (median 0, 40% of output, now cancelled) and **long-form everywhere**: ch1 10–13 min → 1
  view, ch2 90 min → 1 view, while every channel's top video is a **20–60 s Short**.
- Rule of thumb: **do not build long-form until a Short on that topic proves an audience.**

## ✉️ Reading the inbox — no app password needed (2026-11-03)
- Chrome on PC1 has **4 profiles signed into all 4 accounts** (`Local State` info_cache:
  Default=kongkeat.938 · Profile 1=aerismusic8 · Profile 2=kongkeat.p3 · Profile 3=farmmer.938).
- Launch a profile at `https://mail.google.com/mail/feed/atom` → the unread list is plain XML;
  Ctrl+A/Ctrl+C copies it. Automate with `C:\ax-work\_ax\readbox.ps1 -Profile "Profile 3" -Label ch2`.
  The window title is the **URL** (`...feed/atom`), not "Gmail - Inbox for …" — match on `feed/atom`.
- **Chrome cookies cannot be decrypted** (v20 App-Bound Encryption) — do not retry that path.
- `scripts/mail_watch.py` writes mail detail to `~/mail_watch_private.json`, never the public repo.

## 🎙️ K's tone voice — the rule that matters (measured 2026-11-02)
**Never let OpenVoice's converter *produce* the audio.** Used directly it mangles
Thai: F0-contour r 0.26-0.33 ("ไล่"→ไต่/เลย/ไร้, "ทวง"→"ถูก"), centroid 1368→690 Hz
(dull), and it adds a watermark by default. **Fix = `scripts/tts_ktone.py`**:
convert, measure the envelope delta, apply it to the ORIGINAL edge-tts waveform →
r **0.92**, centroid **1223 Hz**. `NARRATOR=openvoice` now means tts_ktone (the old
`tts_openvoice.py` is deleted). `--alpha` 0.35 (brightest) … 1.00 (closest to K,
duller) — **K picks by ear**; that is taste, not a bug. Full episode re-rendered
(17.3 min, verify pass). Listening set: `work/k_voice/watch/ab.html`.
**ASR is not a valid A/B tool here** (gemini-3.5-flash-lite transcribed one file 4
different ways) — use F0-contour correlation + MFCC distance.

## 🧬 Duplicate guard (2026-11-04)
- **A raced CI run can re-upload a live video.** `actions/checkout` pins a run
  to its creation SHA, so two runs on one commit both see a manifest with no
  `video_id`; the loser's `git push` is rejected and its id is lost → a silent
  duplicate (night_120 went live twice: `F4qFHoVpEyI` + `tSgNrHJGVoo`).
- **Fix:** `publish_batch.py` rebases before push AND refuses any title already
  on the live channel (`existing_titles()`), plus `--forget KEY`.
- **Check:** `scripts/check_duplicates.py` (weekly `check-duplicates.yml`).
  Only repeated *titles* count; equal-length Shorts are NOT duplicates.

## 🔬 Reach measured properly (2026-11-04, `docs/COMPARE-2026-11-04.md`)
- `scripts/analyze_reach.py` groups Shorts by hook shape, median views/day,
  comparing only 0.5-8-day-old clips. dharma tonight-action **341.8** vs
  problem **163.0** (2.1x); genx self-truth **463.5**; kongkeat family
  **86.7**. 120-min file ≈ **28x** the watch-hours of the best Short.
- **Ceiling note is a 3h probe now, not a sentence to midnight.** A stale
  note parked 39 ready Shorts ~19h (ch2 accepted 8 uploads the next
  morning). ch2 ceiling ≈ **8-9 uploads/day**.
- **Hour-of-post is confounded with content type** — the dead dharma clips
  are story Shorts, not sleep hooks. Do not credit the hour.

## 🎯 Reach rule (measured 2026-11-04, `docs/HOOKS-MEASURED.md`)
- **dharma (ch2):** a hook that names something to do *tonight* (`ลอง`/`คืนนี้`/
  `เปิดทิ้งไว้`) = **300-570 views/day**; a hook that only restates the problem
  ("ทำไมนอนไม่หลับ") = **74-173**. ch1 = permission hooks (`มีสิทธิ์`/`ไม่ต้อง`/
  `อนุญาต`) 310-373/day.
- Enforced in **two** places: `publish_shorts.py::winning_first()` (publish order)
  and `gen_short_scripts.py::valid(s,cues)` (generation). Do not let the pool
  drift back — that was the defect: 24 losing hooks were queued ahead of 14 winning.
- Long videos (the watch-hour engine) must carry the funnel block too; Shorts did,
  the long ones did not until 2026-11-04.
- **The bottleneck is the shared read quota** (resets 08:00 UTC), not the rails.

## Standing rules
- **AUDIO FIRST**; never claim to have watched/heard — measured numbers only.
- **ak does not upload** — K reviews the first work of each channel.
- **Do NOT invent stories** — build from K's own material in `C:\ax-work\library\<channel>\`.
- A uniform failure = a broken measurement; a scattered one = a real defect.
- **The leak on every channel is the missing next step, not the content.** Shorts are *shown*;
  long-form must *win a click*. ch2 sent 9/14 Shorts onward, ch1 2/16, ch4 3/11. Fix doors and
  hooks before making more clips. Plan + numbers: `docs/CHANNEL-OVERHAUL.md`.

## Channel overhaul (2026-11-03, pushed `ed345b5`)
- Trailer set on all 3 channels + playlists built (`scripts/channel_overhaul.py`, idempotent,
  `--dry-run`). 27 dead-end Shorts given a playlist+home link (`scripts/short_doors.py`).
- One metric to optimise: **Viewed vs Swiped Away** (target ≥60% ch1 / ≥65% ch2 / ≥70% ch4).
  Like-rate is the only *voluntary* signal (ch4 1.99% = best content of the three).
- Advisors agree: do NOT scale output on a losing hook; no quote-only Shorts; no unpaid open
  loops; do NOT delete the old evidence clips; hashtags are not a strategy.
- **Data API throws transient 409 SERVICE_UNAVAILABLE** under bursts — back off and retry.
- **`scripts/pc1_mcp.py`** drives PC1 over raw MCP when the `pc1-winremote_*` tools vanish
  (endpoint in `PC1_MCP_URL`, kept out of the public repo). **chatgpt.com is Cloudflare-blocked
  from the pod**; ChatGPT works only via PC1's signed-in Chrome. Gemini API works from the pod.
- **Push:** use `KONGKEAT_GH_TOKEN`; the `ghu_` URL in `origin` is expired and prompts.

## Shorts rail — now ch1 + ch2 (2026-11-03)
- `publish_shorts.py` / `gen_short_scripts.py` take `--channel dharma|genx`; the
  `CHANNELS` dict holds scripts/manifest/token/work/tags/tail per channel.
  `foreman.py` loops both; `publish-shorts.yml` and `grow-shorts-pool.yml` are
  matrices. **`matrix` cannot be used in a workflow-level `concurrency:` group** —
  put the lock on the job.
- **ffmpeg concat resolves relative list paths against the list file's directory.**
  `make_short.py` wrote relative segment paths → doubled → exit 254 on every local
  build. Always write **absolute** paths into the concat list.
- **Audio rule:** a narrator read has ~18 dB crest factor, so single-pass loudnorm
  cannot hold both -14 LUFS and the ≤ -3 dBFS ceiling (it landed at -1.3 dBTP).
  Use `acompressor(-24dB,6:1)` → **two-pass** loudnorm (`measured_*`,`linear=true`)
  → `alimiter=limit=-3dB`. Measured **-15.0 LUFS / -2.9 dBTP**. -14.0 is not
  reachable on this material; the ceiling wins.
- `content/upload_limit.json` = `{"channels": {<id>: {reset_at}}}` — per channel.
- **Live GenX Shorts (6):** `hcOnVnmzEkc` `NdP1u1yCyCw` `n-BBc8exzXo` `yLVKpRNdD14`
  `Bn_4CHdb2vI` `gQCQkCDZFZc`, all public, each with a playlist + channel door.
- **ch1 can upload; ch2 was capped until 2026-11-04T08:00Z.** ch1 uploads and the
  ch2 long rail are the working channels for volume today.


## 🔒 ตัด K ออก 100% — ตัวตั้งเวลา self-healing (2026-11-07)
- **อย่าพึ่ง GitHub cron**: วัดแล้ว foreman `*/30` ยิงแค่ **1/30 runs**. ตัวตั้งเวลาหลักคือ
  **watchdog chain** (dispatch ตัวเองต่อ) — แก้ให้ **ต่อคิวตัวถัดไป 'ก่อน' ทำงาน** กัน link ตายกลางทาง.
- foreman ชุบ watchdog เมื่อเงียบ + ขับ `check-duplicates`/`progress`/`short doors` เอง; guard = `scripts/test_watchdog.py`.
- pod PAT dispatch = **403** (fine-grained); CI ใช้ `GITHUB_TOKEN` ของตัวเอง (actions:write) ได้.
- เหลือข้อจำกัดเดียว: repo เงียบ 60 วัน → GitHub ปิด cron (แต่ chain ไม่พึ่ง cron).

## 🔁 ออโตเมชันสมบูรณ์ = ทุก rail ต้องถูก foreman ขับ (2026-11-08)
- **นิยามที่ K ต้องการ:** "การทำงานที่ไม่ต้องพึ่ง K คือออโตเมชันที่สมบูรณ์" → ไม่มีงานไหนที่
  รอคนกด. ตัวขับคือ **foreman** (ตัดสินว่าอะไรถึงกำหนด) อยู่บน **watchdog chain**
  (ต่อคิวจริง, cron เป็นแค่ backup).
- **ปิดช่องจริงที่พบ (2026-11-08):** 2 rail มีแค่ `schedule` ไม่มีใครขับ → `studio-ai`
  (สมองเรียนรู้ที่อ่าน Analytics → ป้อนหัวข้อให้ pool) และ `fetch-music` (เพลงพื้น Shorts).
  เพิ่ม rule ใน foreman แล้ว. + `selftest` ใหม่.
- **เทสต์ที่ไม่มีใครรัน:** 5/8 guard (channel identity, chapter, music beds, remake, Short
  art/music) ไม่มี CI caller → สร้าง **`selftest.yml`** รันทั้ง suite (ไม่กี่วินาที) ให้
  foreman ขับรายวัน. CI run 42439933204 = **success, 8/8 ผ่าน**.
- **guard กันหลุดซ้ำ:** `test_watchdog.py` บังคับว่า **ทุก workflow ยกเว้น `foreman`/`watchdog`
  ต้องถูก foreman อ้างถึง** → เพิ่ม rail ใหม่แบบ schedule-only จะ fail ทันที ไม่เงียบ.
- **หลักการ:** "ออโตเมชันสมบูรณ์" ไม่ใช่แค่ทุกอย่างมี cron — ต้องมี **ตัวขับที่เชื่อถือได้
  (chain) + guard ที่บังคับให้ rail ใหม่ต้องถูกขับ**. เช็คเร็ว: `python3 scripts/foreman.py --dry-run`.

## 🌉 "ak ทำแทน K" ได้แค่ไหน + สะพาน PC1 (2026-11-08)
- **ทำแทน 100% ไม่ได้:** (1) pod browser → Google **ถูกบล็อก** (`signin/rejected`
  "browser may not be secure") (2) App password K สร้างไม่ได้ (3) **PC1 = 502**
  backend-down (`winremote-mcp` ดับ) + ไม่มี inbound route ให้ pod สตาร์ทโปรเซส.
- **ทางเดียวที่อ่านเมล์ได้ = Chrome บน PC1** (login ค้าง 4 บัญชี, ผ่าน `feed/atom`).
  ⇒ ทุกอย่างขึ้นกับ "PC1 ออนไลน์" → **ต้องมีคนที่เครื่อง (หรือ ChatGPT ที่รีม็อต PC1) รันซ่อม**.
- `scripts/pc1_health.py` (+guard) แยก **up / backend-down / auth / offline** (4 อย่าง
  4 วิธีแก้); `account-watch` รันเมื่อ inbox BLIND. วัดสด = **backend-down**.
- `ops/pc1_fix_remote.ps1` คัดลอกเข้า **public repo** → ลิงก์ถาวรให้ ChatGPT:
  `raw.githubusercontent.com/kongkeat938/ai-content-lab/main/ops/pc1_fix_remote.ps1`
  (200 ✓, ไม่มีรหัสฝัง). Brief: `docs/PC1-BRIDGE-2026-11-08.md`.

## 🔌 ทางถาวรสู่ PC1: self-hosted runner (2026-11-08)
- **pod สั่ง PC1 ตรง ๆ ไม่ได้เลย** (วัดครบ): funnel 502 · ports 22/3389/5900/8090/12000 ปิด ·
  rendezvous host เก่าตายหมด (pod รีไซเคิล+เปลี่ยนชื่อ) · ไม่มี runner ใน repo.
- **ทางยั่งยืน = GitHub Actions self-hosted runner บน PC1** (PC1 dial ออกเอง; ไม่มี inbound;
  รอด pod รีไซเคิล). **ak ออก registration token ได้** (มี admin):
  `gh api -X POST repos/kongkeat938/ax-workspace/actions/runners/registration-token -q .token`.
- ติดตั้ง: `ops/pc1_install_runner.ps1` (logon task — service account เห็น Chrome ไม่ได้;
  idempotent; ไม่เก็บ token) → แล้วสั่งงานด้วย `gh workflow run pc1-task.yml -R
  kongkeat938/ax-workspace -f task=status|fix-remote|readbox`. Doc: `docs/PC1-RUNNER-2026-11-08.md`.
- **ตัดออกแล้ว:** Google **device flow + Gmail = `invalid_scope`**; OAuth YouTube scope = แค่
  `youtube`; แต่ pod **เข้า imap.gmail.com:993 ได้** ⇒ ถ้ามี app password อ่านเมล์จาก pod ได้เลย.

## 📧 เก็บรหัสผ่านเมล์ (K: กรอกครั้งเดียว ใช้ทุกบัญชี) — 2026-11-08
- **เก็บที่ GitHub Repository Secret ชื่อ `IMAP_ACCOUNTS`** (JSON หลายบัญชีในค่าเดียว);
  ไม่มีรหัสใน git (repo public). เอกสาร `docs/MAIL-CREDENTIAL-2026-11-08.md`.
- **⚠️ Gmail ไม่ให้ใช้รหัสผ่าน login จริงผ่าน IMAP** — ต้อง **App Password** และ
  **app password ผูกกับบัญชีเดียว** ⇒ "รหัสเดียวใช้ทุกบัญชี" ไม่มีจริง. ที่ทำได้ =
  1 บัญชี 1 app password แต่ยัดใน secret เดียว ⇒ K กรอกครั้งเดียว. ทางเลือก: Gmail
  Delegation หรือ scope `gmail.readonly`.
- **สถานะ:** ชั้นอ่านเมล์ = **BLIND** (ยังไม่มี cred; token ทั้ง 4 = scope `youtube`
  อ่านเมล์ไม่ได้). รอ K ใส่ `IMAP_ACCOUNTS`.
- `mail_watch.py` รับ `IMAP_ACCOUNTS` (list/dict) + `IMAP_USER`/`IMAP_APP_PASSWORD` เดิม;
  guard `test_mail_credentials.py` (กันรหัสหลุดในรายงาน). เทสต์ **12/12**.

## 🔎 PCSEV — "verify จากอะไร" (2026-11-08)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** K ถามขั้น V ควรตรวจจากไหน.
  คำตอบ: **จากแหล่งที่วัดได้จริง ณ ปัจจุบัน ไม่ใช่เอกสารที่ commit ไว้** (เอกสาร=คำอ้าง
  อีกชั้น). ลำดับ: **API สด > ไฟล์จริง(ffprobe) > เทสต์ที่ล้มได้ > เอกสาร(อ่อนสุด)**.
- **เจอ 2 จุดที่เอกสารผิด (วัดสด):** (1) `report_reach.py` อ้างว่า Analytics API ปฏิเสธ
  token — จริง ๆ **ได้ทั้ง 3 ช่อง** (รวม `audienceWatchRatio`=retention curve); แก้แล้ว.
  ที่ API ไม่มีจริง: `impressions`/CTR (400) + รายได้ (scope ไม่พอ). (2) `docs/watch_hours.json`
  **คลาดเคลื่อน 52-244%** จาก live (genx 5,743→19,760) เพราะ API **รายงานย้อนหลังช้า ~2 วัน**.
- **⭐ K ต่อยอด:** แหล่ง verify ที่ดีสุด = **counter ที่ต้องโต** (lifetime views/watch/subs)
  เพราะแบก invariant ในตัว: **ห้ามลดลง** (ลด=ข้อมูลผิดแน่นอน) · **ห้ามนิ่ง** (นิ่ง=ช่อง/pipeline
  หยุด) · ledger append-only = หลักฐานว่าตรวจแล้ว. snapshot บอก "ตอนนั้นเท่าไหร่"; counter
  บอก "ตอนนี้ยังเดินอยู่ไหม".
- **เครื่องมือ:** `verify_claims.py` (วัดซ้ำเทียบ snapshot, `--strict` ให้ exit 1) ·
  `counter_ledger.py` (append `docs/counters.jsonl` + ตรวจ 2 invariant; ลด=exit 1, นิ่ง≥3วัน=flag) ·
  guard `test_verify_claims.py` + `test_counter_ledger.py`. เทสต์ **11/11**.
- **Data API quota หมด (403) ห้ามตีว่า "ไม่มีข้อมูล"** — Analytics API quota แยก ยังตอบ
  (ใช้หน้าต่าง `2020-01-01..today` เป็น counter สะสม: genx 23,681 · dharma 10,861 · kongkeat 5,645).
- เอกสาร: `docs/PCSEV-VERIFY-2026-11-08.md`.

## 🏢 โมเดลธุรกิจ + ทีม 5 agent + QA critic (2026-11-08)
- K: "ak สร้างทีม developer ... ออกแบบโมเดลธุรกิจเลย". เอกสาร: `docs/BUSINESS-MODEL-2026-11-08.md`.
- **Panel 3 ค่าย เอกฉันท์:** คอขวดจริง = **retention/AVD ไม่ใช่เพดานอัปโหลด** (ใช้แค่ ~2.8
  ชม./วัน). **$500/ช่องใน 6-12 เดือนไม่จริง** → 18-36 เดือน; เป้าตั้งต้น $50-100/ช่อง.
  **ทุ่ม dharma ก่อน** แล้วก็อปโมเดล. ลำดับ: retention → CTR → niche → ปริมาณ(สุดท้าย).
- **ทีม = 5 agent:** Strategist(`studio_ai.py`) · Scriptwriter(`gen_*_scripts.py`) ·
  Producer(`make_compilation`/`make_chapter_video`) · Publisher(`publish_*`) ·
  **QA/Critic(`qa_gate.py` — สร้างใหม่วันนี้, veto ได้)**.
- **QA gate:** เกรด A-D จาก receipt. veto เมื่อ: verifier fail · ไม่มี hook (2-30 วิ) ·
  <2 การ์ด หรือการ์ดใด > 8 นาที · TP > -3 dBFS. veto → `state=blocked` →
  `publish_batch` ไม่อัปโหลด. ผูกทุก long-form rail ผ่าน `add_release_to_manifest.py`.
  **dharma build จริง = เกรด A**; guard = `test_qa_gate.py`. CI 42442103719 = 9/9 ผ่าน.
- **หลักการ:** ประตูอนุมัติที่ดี ≠ "รอคน" แต่คือ **gate ที่วัดได้ + บล็อกเองได้**.
  "ออโต้" ที่ไม่มี critic = automate การปล่อยของเสีย.

## 🔍 คลิปวิว 0 — ต้นเหตุจริงคือ burst ไม่ใช่คุณภาพ (2026-11-07)
- **Analytics รายงานคลิปใหม่ช้า** — คลิปที่ขึ้น '0 วิว' ใน Analytics จริง ๆ มี 154/107/75
  (Data API). **อย่าใช้ Analytics ตัดสินคลิปใหม่** ใช้ Data API `statistics.viewCount`.
- **ต้นเหตุวิว 0 = อัปโหลดรัว**: ch2 ยิง 25 คลิปใน 10 นาที → 20 วิว 0. คลิปที่ปล่อยทีละ 1-2 = 100-1,000 วิว.
- แก้: `publish_shorts.py` per-run=1, `MIN_GAP_HOURS=2`, workflow 3 รอบ/วัน ห่าง 8 ชม. +
  `scripts/diagnose_videos.py` (วินิจฉัย+burst→RULES→insights) รันใน studio-ai ทุกวัน.
- เอกสาร: `docs/ZERO-VIEW-DIAGNOSIS-2026-11-07.md`.

## yt938-1 status — measured live 2026-10-31 14:45Z
- **ch1** ตาต้า GenX Shop 33 vids / 6 subs · **ch2** Farmmer 10 vids / 7 subs · **ch4**
  kongkeat pratumma 8 vids / 6 subs. ch1 ep01 `E1gxiblSUo0` is **still private** (K has not
  released it); the public ch1 Short `CaVSO74wFms` has 15 views.
- **Auto-publisher ledger = 4** (`docs/published.json` in ax-workspace): ch2 `wIpNM1gqPYc`,
  ch2 `oIsloIKa0J4`, ch1 `CaVSO74wFms`, and **ch4's first auto-Short `Wr5N-NfhGMM`**
  (2026-10-31T14:38Z, public, 25 s). Rotation across all three channels is now proven live.
- **✅ GitHub Actions cron DOES fire here** (corrected 2026-11-07; the old note said total=1
  and "manual dispatch only" — wrong). `runs?event=schedule` = **42 runs**, latest
  2026-11-07T02:56Z, all green (set-thumbnails / grow-shorts-pool / publish-ch4 /
  publish-batch / publish-shorts / link-shorts). Root cause of the old belief: `foreman.yml`
  had **no `schedule` of its own** (push + dispatch only), so the driver looked dead between
  pushes. Fixed: foreman now carries `*/30 * * * *`. `watchdog.yml` also self-chains every
  ~2 h. Treat the pipeline as **autonomous — nothing waits on a person**.
  Safe failure mode: `--slot-hours` + the ledger mean a dropped tick costs a post, never a
  double-post. Detail: `ax-workspace/docs/AUTOMATION.md` + `2026-11-07.md`.
- **edge-tts female voice re-measured** (6 lines × 3 tries): `th-TH-PremwadeeNeural` 3 ok /
  3 fail, `th-TH-NiwatNeural` 6 ok / 0 fail → ch1's female-voice re-render is still blocked.
- **Real bottleneck is content, not the rail:** per-channel `scripts/` on PC1 are empty; the
  rail is proven. Thai scripts + render is what "ปั้นช่อง" needs.

## 🏷️ ch4 name/handle (2026-11-05, K: "ไม่อยากใช้ชื่อนี้บนคลิป")
- Channel TITLE is already **เรื่องเล่าการ์ตูน**. The **HANDLE** is still `@kongkeatpratumma`
  (a personal name). **The Data API CANNOT rename a handle** -- K must do it in YouTube Studio
  (Settings > Channel > Handle). Available as of 2026-11-05: @ruenglaokatoon, @ruenglaocartoon,
  @storycartoonth, @ruenglao, @niThaanCartoon (checked via 404 on youtube.com/@<h>).
- No watermark/name is burned into the video; the only place the name showed was the
  description tail. Fixed everywhere with the **name-free channel URL**
  `https://www.youtube.com/channel/UC7gCIu4G_7QCEJ8hJ-34zoQ`.
- **Live repair done:** `scripts/scrub_channel_name.py --channel ch4 --apply` rewrote the
  descriptions of 27 ch4 uploads (idempotent; also repairs a doubled `youtube.com/https://`
  that a first pass introduced). Other scripts/tails (publish_shorts, short_doors,
  promote_channels, ch2_publish cross-links, channels.json, report/analyze labels) now
  carry no personal name either.

## 🚀 ch4 on the Shorts rail — LIVE (2026-11-05)
- K handed ak administration ("บริหารเองต่อได้เลย"). Decision: scale the channel that already
  works. ch4 had pivoted to family moments organically but was publishing by hand.
- Wired `kongkeat` into `publish_shorts.py` (tags/category/cues/tail), the `publish-shorts.yml`
  matrix + trigger paths, `grow-shorts-pool.yml`, and `foreman.py` (upload-cap tracking).
- **Proven live:** the push triggered publish-shorts and the ch4 job published **6 Shorts
  automatically** (ch4 videos 18→24; ids in `content/ch4_shorts.json`). ch4 now drips on the
  same rail as ch1/ch2. Decision record `docs/DECISIONS-2026-11-05.md`.
- Note: `grow-shorts-pool.yml` + `publish-shorts.yml` matrix channel key is `kongkeat-story` for
  the generator but `kongkeat` for the publisher -- keep that in mind when editing either.

## ⏳ Time-to-results (measured 2026-11-05)
- K asked how long until results. 90-day reality (3 channels): Shorts 9,947 views / 30.6 h;
  **long-form 383 views / 3.35 h** (long-form is what counts toward YPP watch hours).
- YPP: 1,000 subs + (4,000 long watch-h OR 10M Shorts views/90d). Gap: watch-h ~300×,
  Shorts views ~1,000×, subs ~12×. **Feb 1 2027 thresholds DOUBLE** (8,000 h / 20M views).
- Watch-hour per view: long-form 0.0062 vs Shorts 0.0018 → long-form ~3.4× more efficient per
  view. Honest verdict: monetization is NOT reachable in 1-2 years at this rate; near-term
  deliverable = the working agent + audience growth. `docs/TIME-TO-RESULTS.md`.

## 🧪 Multi-model script panel (2026-11-04) — K's "หลาย AI คัดกรองบท"
- `scripts/panel_script.py` = the vetting step: several models score a draft 0-100, list
  weak points, propose a revision; the highest-scoring revision that still passes `valid()`
  wins, 2 rounds. Votes are written to `<input>.panel.json` (auditable, not a black box).
- `gen_short_scripts.py` now runs the panel on every fresh draft (`--no-vet` to skip).
- **Voters measured 2026-11-04:** `gemini-3.1-flash-lite` + `gemini-3-flash-preview` reliable;
  `gemini-3.5-flash-lite` 503s intermittently; `gemini-2.5-*` retired (404); `gemma-*` 500;
  **Pollinations anonymous = 1 reply/45 s per IP** and truncates long JSON (needs
  `reasoning_effort:low` + `max_tokens`, still rate-limited). Independent voters: a busy one
  lowers the vote count, never the run. Proof: a losing-shape draft scored 65 → 92 after vetting.
- Formula doc: `docs/CONTENT-FORMULA.md`.

## 🎯 ch4 "เรื่องเล่าการ์ตูน" pivoted (2026-11-04)
- Measured: classical tales มัทนะพาธา 1 view, ไกรทอง 5, จดหมายจากสิบปีก่อน 6; but specific
  family moments — แม่ทำกับข้าว 1,083 views / 103.6% watch, คุกเข่าขอโทษพ่อ 460 / 115%.
- **ch4 thumbnail gate CLEARED (2026-11-05):** after K's verification, `thumbnails.set` on ch4
  returns **SET OK 3/3** (was 403 "doesn't have permissions"). No verification gate remains
  anywhere — thumbnails work on all channels via API. ch4 is now in `gen_short_scripts.py`
  (`--channel kongkeat-story`), so the pivot can produce content.
- **Both vendors (Gemini + Pollinations) said `pivot`.** ak decision: drop classical tales as
  the main line; the channel now does **specific family moments (relationship + physical act)**.
  `docs/STORY-CHANNEL-PIVOT.md`; CONTENT-PLAN.md carries a warning banner.

## ✅ K verification done (2026-11-04)
- K completed **phone verification + advanced features**. API confirms `longUploadsStatus=allowed`
  on all 3 channels; avatars/banners set; **all 7 ch2 thumbnails were already live via the Data
  API** (so the API thumbnail path never needed verification — the old 'K must verify to set
  thumbnails' belief was wrong).
- Real gap found and fixed: every channel had **empty `channel.keywords`** (feeds search +
  related-channels rail). `scripts/set_channel_seo.py` sets them by reading branding first and
  writing only keywords back (a blind `channels.update` wipes the banner). Applied + verified
  live on dharma/genx/kongkeat-story.

## 🤝 Advisor panel — MUST be 3+ vendors (`scripts/advise.py`, 2026-11-05)
K's rule: recurring K-only blockers go to other AI vendors; whichever solves it becomes a
standing advisor. **K corrected ak: a single advisor that "falls over" is a failure — keep
at least 3 AI vendors on the panel.** `scripts/advise.py` asks all of them and reports who
answered (one dead vendor must not stop a decision).
| # | vendor | route | status 2026-11-05 |
|---|---|---|---|
| 1 | **Gemini** | `GEMINI_API_KEY`, tries 3.5/3.1-flash-lite/flash-lite-latest | ✅ 200 |
| 2 | **Pollinations** | `text.pollinations.ai` model=**openai**, no key | ✅ 200 (most other models 402) |
| 3 | **OpenHands Cloud** | `KONGKEAT_OH_KEY` → `POST /api/v1/app-conversations` (own DeepSeek agent), poll events | ✅ works, ~2-4 min |
- **Unreachable (do not retry blindly):** ChatGPT (PC1 CDP 9222 → **404**; port open, chrome.exe pid), DeepSeek (login), Devin (`DEVIN_API_KEY` 403), DuckDuckGo AI (**ERR_BN_LIMIT**, needs JS challenge), DeepInfra (needs key), HF (needs token). `llm-proxy.app.all-hands.dev` needs a per-conversation token, not the API key.
- OpenHands event shape: reply is `source="agent"` (not "assistant"), `kind=MessageEvent`,
  `message.content` = list of `{type:text,text:...}`. `start-tasks?ids=` returns a **list**.
- Detail: `docs/CONSULT-2026-11-04.md` (section "แก้ 2026-11-05").

## 🤝 Vendor consult (2026-11-04) — K's "ask other AI vendors" loop
- K's rule: recurring K-only blockers go to other vendors; whichever solves it becomes a
  standing advisor. Detail: `docs/CONSULT-2026-11-04.md`.
- **Reachable from the pod:** Gemini API (free key; `gemini-3.5-flash-lite` works,
  `2.5-flash`/`2.0-flash` are retired) and **Pollinations text** (`text.pollinations.ai`,
  no key, 200). **ChatGPT = only via PC1's logged-in Chrome** (its CDP 9222 was dead today).
  **DeepSeek needs a login** on PC1. **Devin `DEVIN_API_KEY` on PC1 = 403, unusable.**
  HF inference needs a token (old `api-inference` endpoint is gone; `router.huggingface.co` = 401).
- **Advisor pick:** ChatGPT primary (most concrete), Gemini API secondary (automatable).
- Consult outcome: (P1) **no legitimate custom-thumbnail bypass exists** — ChatGPT + Gemini
  agree; the free move is a **title-card in the first frame**. (P2) image path that needs no K:
  **SVG/Pillow + Wikimedia Commons + Pexels API** (`PEXELS_API_KEY` exists on PC1).
  (P3) confirms the loop lever (avg% > 100%) and shifting Shorts → long-form.

## 🌐 No-browser path — YouTube Data API from CI (2026-11-03)
- **Studio UI blocked by phone verification + pod recycles kill the browser login → do
  NOT ask K to log in. Use the Data API.** Creds are repo secrets; a GitHub Actions job
  runs it unattended. Detail: `topics/04-no-browser-api-path.md`.
- Rail: `scripts/set_thumbnails.py` + `content/ch2_thumbnails.json` +
  `.github/workflows/set-thumbnails.yml` (08:07/09:07/10:07/11:07 UTC). Quota =
  deferral, not failure; resets 08:00 UTC. Proven live (auth + call reach YouTube).
- Do NOT trust old video-id lists — `9bytRcx7SaY` (404 everywhere) and `Mv0jl7KhxIE`
  are not live. Pod IP gets throttled by YouTube after a few fetches.

## 🖼️ Image/music quota — measured 2026-10-31 (NOT an account-count problem)
K ordered: "ถ้า Gemini/Flow ลิมิตเต็ม ให้สมัครเมล์ใหม่สร้างบัญชีเลย". Measured first — the
limit is **service-wide**, so new accounts would not help and risk banning the real
channels (Google forbids multi-account evasion; repo rule in `PROMPT-for-chatgpt-remote.md`
says "ห้ามสลับบัญชี เด็ดขาด"). **No accounts created.**
- Gemini API `$GEMINI_API_KEY`: valid (200) but **every image model → 429 `limit: 0`** on
  free tier → a new GCP project also gets 0. Pollinations `model=flux` → 200 but retries →
  **402 service-wide cap**. **Only working image/music path = drive the signed-in PC1
  browser** (`ops/gemini_batch.py`, `ops/flowmusic_batch.py`). Shorts do NOT need images.
  Pod-local alt: `scripts/start_novnc.sh` (chromium + CDP on 9222).
- K decision recorded (`docs/NEEDS-K.md` #6) with 3 safe options: PC1 session / paid
  billing (needs K) / retry Pollinations off-peak. Brief: `docs/PLAN-BRIEF-for-chatgpt.md`.

## 🔊 Free tools that WORK (measured 2026-10-31, `ax-workspace/docs/FREE-TOOLS-MEASURED.md`)
- **gTTS** (Google Translate TTS, free, no key) → **female Thai voice**, 5/5; it renders the
  exact line edge-tts fails on. `short_maker` now falls back to gTTS for a female voice
  instead of flipping to the MALE voice — **this unblocks 42 of 60 ch1 entries** (ch1's
  female-voiced ones). Guard: `ops/test_voice_fallback.py`; workflow installs `gTTS`.
- **Gemini text `gemini-3.5-flash-lite`** works on the free key (200, 3/3) and writes usable
  Thai copy → the free source for scripts/planning. (`gemini-3.8-flash` = 503, do not use.)
- **Wikimedia Commons API** → real images + licence (for ch4 story videos). Openverse times
  out from the pod. Piper Thai is unusable (`tltk`→scikit-learn build fails on py3.13).

## 🔑 Standing principle (K, 2026-11-07): everything is an algorithm
"มันแค่อัลกอริทึม แค่รู้และเข้าใจก็เจาะเข้าไปแก้ได้ทุกปัญหา ทุกเป้าหมาย" — a wall is
almost always a rule I have not read yet, not an impossibility. When a paid tool dies,
a free one does the job (proved 2026-11-07: Tavily → Gemini free API + r.jina.ai +
Wikipedia + gTTS; image gen blocked on Gemini/Pollinations → **Wikimedia Commons** works).
Two duties follow, both non-negotiable:
1. **Read the vendor's own rule** before declaring anything impossible. The rename
   "wall" was `part` taking one value + `brandingSettings.channel.title` being
   non-writable (`channelTitleUpdateForbidden`) + `localizations.(key).title` being the
   writable field, needing `defaultLanguage` first. Seven days were lost to guessing.
2. **An LLM is not a primary source.** Gemini confidently said the API cannot rename a
   channel; the official reference says otherwise. Confirm against vendor docs or a live
   measurement, never against a model's opinion.
**The one genuine boundary:** identity/account ownership. No free tool substitutes for
being the account owner. Do not hunt for one; remove the step from the critical path.

## Authority (2026-10-31)
**ak** holds K's grant to administer and decide ("อนุมัติให้บริหารงาน และตัดสินใจแทน k ได้เลย"). ak acts alone on reversible/internal work; still asks K before publishing, enabling automations, deleting history, or renaming. Charter + log: `ax-workspace/.openhands/memory/DECISIONS.md`.
- **API ตั้งชื่อช่อง/แฮนเดิลไม่ได้ (วัด 2026-11-07):** PUT `part=localizations` (key **`th_TH`** ไม่ใช่ `th`)
  คืน 200, `description` ติด, แต่ `title` กลับมาเดิม → ต้องเปลี่ยนชื่อ+แฮนเดิลใน **Studio** เท่านั้น.
  แฮนเดิลเปลี่ยนได้ **2 ครั้ง/14 วัน**. สคริปต์: `scripts/set_channel_name.py`.
- **แบนเนอร์ช่องติดตั้งผ่าน API ได้ · อวตารไม่ได้ (วัด 2026-11-07):** `channelBanners.insert`
  (uploadType=media) → URL → ผูกด้วย `channels.update?part=brandingSettings` +
  `brandingSettings.image.bannerExternalUrl` (**echo `brandingSettings.channel` เดิมกลับทั้งก้อน**
  ไม่งั้น description/keywords หาย). **อวตารไม่มี API** → Studio เท่านั้น. สคริปต์ `scripts/set_channel_art.py`.
  สร้างภาพ: `scripts/make_branding.py --style lavish` (safe zone: ข้อความต้องอยู่ในโซน desktop 1235×338).
- **⚠️ กฎภาพช่องจาก K (2026-11-07): พื้นหลังต้องสว่าง + ตัวหนังสือสีเข้มเสมอ ห้ามพื้นหลังมืด ทุกช่อง.**
  ตัวหนังสือต้อง contrast ≥ 4.5 กับพิกเซลหลังมัน (วัดจริง ไม่เดา). **อวตาร = ลายอบอุ่น ไม่ใช่รูปคน**
  (K: "รูปผู้หญิง ผู้ชาย ไม่เอา"). สร้าง: `scripts/make_branding.py --style lavish` (สว่างทั้ง lavish+classic).

## 🤖 ระบบออโต้ 100% (2026-11-07) — K ไม่อยู่ในวงจร
- **คอขวดเดิม = ขาด "สมอง" ไม่ใช่ขาด rail.** rail มีอยู่แล้ว: 20 workflow, foreman heartbeat
  (ทุก 30 นาที), watchdog self-chaining, publish-shorts/batch/ch1/ch4, grow-shorts-pool.
  **ไม่มี approval gate เลย** และ **secrets ครบใน GitHub** (YT_CH1-4 + client + Gemini).
- **ของใหม่ที่ปิดวงจร:** `scripts/studio_ai.py` (YouTube **Analytics API** → panel → เขียน
  `content/insights/<ch>.json`) + `.github/workflows/studio-ai.yml` (cron 21:45 UTC, matrix
  ch1/ch2/ch4). `gen_short_scripts.py` อ่าน insights ก่อน → คลิปใหม่ตามสิ่งที่ได้ผลจริง.
- **YouTube Studio UI ใช้บนคลาวด์ไม่ได้** (302 → accounts.google.com; pod/cloud browser/curl
  เจอหมด) และ Inspiration tab ไม่มี API → `studio_ai.py` คือตัวแทน (Analytics API ตอบ 200
  ด้วย refresh token ของช่อง).
- **ตัวเลข 28 วัน (2026-11-07):** ch1 14,558 · ch2 9,605 · ch4 4,131 · ch3 1,039 views.
  ch4: Shorts ครอบครัวอารมณ์แรง ดูจบ 103-115% vs นิทานยาว 6 วิว 10.8%.
- **K เหลือเกี่ยวแค่:** เพิ่มช่องใหม่ (OAuth) + อัปโหลดอวตาร (ครั้งเดียว). แบนเนอร์ = API ทำเอง.
- Pages: https://kongkeat938.github.io/ai-content-lab/ (source `/docs`, branch main).
- เอกสาร: `docs/AUTONOMY-2026-11-07.md`, `docs/CONTENT-IDEAS-2026-11-07.md`.
- **กับดัก:** overlap filter สำหรับหัวข้อที่เรียนรู้ต้องใช้ floor 8 ตัวอักษร (floor 3 กรองทิ้ง 8/8
  บนช่องที่ pool เต็มไปด้วยเรื่องครอบครัว); ใช้ vendor แรกที่ให้หัวข้อใช้ได้ (Gemini สะอาด,
  Pollinations เพี้ยน).

## 🔍 ประเมินคุณภาพรายคลิป (2026-11-07)
- `studio_ai` เดิมแค่จัดอันดับด้วยวิว **ไม่ประเมินคุณภาพ** → สร้าง `scripts/video_review.py`:
  เกรด A–D จาก retention (`averageViewPercentage`) + engagement (likes+comments+shares+subs ต่อ 1k
  views) เทียบค่ากลางช่อง → panel วิจารณ์ hook/lines/cta จริง → `content/reviews/<ch>.json`
  + `docs/REVIEW-<ch>.md` + สกัด **RULES 3 ข้อ** เข้า `content/insights/<ch>.json`.
- `gen_short_scripts.py` ฉีด rules เข้า prompt → คลิปใหม่ปรับตามคำวิจารณ์ (พิสูจน์แล้ว
  "applying 3 rules learned from the video review").
- **กับดัก:** Data API quota หมดกลางวันได้ (403, รีเซ็ต 08:00 UTC) → ชื่อคลิปหายแต่เกรดยังได้;
  จับคู่สคริปต์ผ่าน manifest `content/<ch>_shorts.json` (video_id→script id). Analytics quota
  แยกจาก Data API.
- workflow `studio-ai.yml` มี step "Grade the videos already on the channel" (if: always()).

## 🚦 เพดานอัปโหลด (2026-11-07)
- **ต้นเหตุวิว 0 ที่แท้จริง:** `publish-shorts.yml` trigger `on: push` เมื่อ `scripts.json` เปลี่ยน →
  pool grow ทุกครั้งยิง publish อีก. วัด 24 ชม.: dharma 23 · genx 20 · kongkeat 27 คลิป →
  45 คลิป ch4 วิว 0 (คลิปที่ปล่อยช้าได้ถึง 1,088).
- **แก้:** `DAILY_CAP=3` + **ledger ที่ commit เอง** (`content/upload_log.json`, `note_upload()`).
  ⚠️ รอบแรกนับจาก git log **ไม่ทำงานใน CI** เพราะ checkout เป็น shallow (fetch-depth 1).
  พิสูจน์ใน CI จริง: "daily cap reached (29/3 ...)". K แก้เพดานที่ `DAILY_CAP`.
- **token dispatch workflow ไม่ได้ (403)** — ระบบเดินด้วย schedule + push เท่านั้น.
- เอกสาร: `docs/QUALITY-FINDINGS-2026-11-07.md`.

## 🎨 Shorts มีภาพ+เพลงจริงทุกช่อง (2026-11-07) — รายละเอียด `2026-11-07.md`
- **ภาพ:** `assets/art/ch1|ch2|ch4/` (Openverse, licence gate, `credits.json`); `make_short.py
  --art-dir` + `pick_art()` = hash(id) → รูปคงที่ต่อคลิป; ภาพ blur 6px ใต้ scrim.
- **เพลง:** **AERIS pack (CC0-1.0)** จาก K: `raw.githubusercontent.com/aerismusic8-alt/
  aeris-drive-automation/main/share/aeris-music/catalog.json` → `beds/` 6 อัน **บรรเลงล้วน**.
  `scripts/fetch_music.py` → `assets/music/<mood>-bed-<mood>.mp3` (-22.6 LUFS).
  mood: dharma=calm · genx=hopeful · kongkeat=warm → `pick_bed()` จับคู่.
- **❌ yt-dlp ดึง YouTube ไม่ได้เลย (4 runner × ทุก client)** — ต้องมี account cookie.
  ดึงเพลงจากช่องตัวเองแบบไร้คน = ทำไม่ได้; ใช้ไฟล์ที่เจ้าของให้แทน.
- ต่อเข้า `publish_shorts.py` แล้ว (`--art-dir`+`--music`); test `scripts/test_short_art_music.py`;
  CI `fetch-music.yml`. วัด: 3 ช่อง -15.9…-16.6 LUFS, TP ≤ -2.87.
- **env:** pod recycle ล้าง ffmpeg + pip deps → ติดตั้งใหม่ได้ทุกครั้ง.

## 🔑 Durable: "แยกไม่ได้" ≠ "ผิด" (quota-safe identity)
ตัวตรวจที่พิสูจน์ตัวตนด้วย **Data API** (`channels.list`) จะ **ตายเงียบเมื่อโควตาหมด**
(403 ทุก token) แล้วอ่านผลเป็น "ไม่ใช่ของเรา". ทางแก้ที่ repo ใช้: **per-channel secret
คือตัวตน** (`YT_CH1/2/4_REFRESH_TOKEN` = ช่องนั้นโดยโครงสร้าง) — fallback เมื่อ API แยกไม่ได้,
แต่ token ที่ยืนยันได้ว่าเป็นช่องอื่นยัง abort. ใช้ใน `yt_auth.CHANNEL_ENV` +
`env_token_for_channel`; เทสต์ `scripts/test_channel_identity.py`. **cron ที่รัน
ก่อน 08:00 UTC จะอยู่ในหน้าต่างโควตาหมดเสมอ** (Data API รีเซ็ต 08:00 UTC; Analytics แยกโควตา).

## ⏱️ Long-form rail: `--minutes` is a FLOOR, not a target (2026-11-08)
- `build_night.py --minutes N` loops the whole talk until it reaches N minutes. If the
  content set is *under* N, the talk is heard **twice** (a 28.5-min set under `--minutes 30`
  shipped as **57.1 min**, title still saying "30 นาที"). Size the set so **one pass already
  exceeds the floor**; never rely on `--minutes` to trim.
- **Quota split:** `videos.insert` draws its own pool, so an upload can succeed while
  `videos.delete`/reads 403 all day on the spent read pool. Queue deletes for **08:12 UTC**
  (after the 08:00 reset, before publish-batch's 09:17 tick). `scripts/delete_video.py` +
  `.github/workflows/delete-video.yml` = guarded delete; `remove-bad-cut.yml` = the scheduled
  cleanup. `publish-batch.yml` also fires on **push to `content/ch2_publish.json`** — a build's
  manifest commit auto-uploads with no dispatch.
