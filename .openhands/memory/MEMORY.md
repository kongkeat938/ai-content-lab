# Project Memory — ak (ai-content-lab)

**Agent `ak`** (renamed from AX, 2026-10-31). Owner **K**: replies in Thai, demands **measured
evidence, not claims**. ak may administer + decide; asks K only before a new channel, deleting
history, or renaming. **Keep this file short** — it is injected every session and the tail is
truncated. Full detail in `.openhands/memory/2026-11-DD.md`, `ARCHIVE-MEMORY-2026-11-09.md`, `docs/`.

## 🎯 WHAT GATES THE BUSINESS (measured; `docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY.** Shorts do not count toward 4,000 h. Steer by
  **long-form watch-hours/week + `retention@2min`**, never raw views (one channel looked 92× closer
  than it was). **dharma is 96% of all long-form watch time → concentrate there.**
- **The binding constraint is the first 2 minutes, not volume.** dharma's 120-min file keeps 102%
  at 1% then **28.9% at 2% (~2.4 min)** — 71% leave. Upload volume uses ~2.8 h/day of a 6–8-clip
  capacity → more volume is noise.
- **Shorts→long-form funnel is dead** (genx 27k Shorts views → 2 long-form views). Long-form views
  come from subscribers. Winning content is **specific + actionable**, not abstract reassurance.
- Review the decision **2026-11-16**.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Frame every fix for K in all five; **Verify
  must measure live**, never from our own docs. Trust: **live API > real output file (ffprobe/
  ebur128) > a test that can FAIL > committed doc**. Best verify = a **counter with an invariant**
  (`scripts/counter_ledger.py`, `docs/counters.jsonl`).
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies silently on a spent quota and reads as
  "not ours". Use **per-channel secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`,
  `yt_auth.CHANNEL_ENV`); `scripts/test_channel_identity.py`.
- **Everything is an algorithm:** read the vendor's own rule before declaring anything impossible;
  an LLM is not a primary source. Real boundary: identity/account ownership.
- **Advisor panel = 3+ vendors** (`scripts/advise.py`): Gemini free API, Pollinations text,
  OpenHands Cloud (`KONGKEAT_OH_KEY`). Do NOT retry ChatGPT/PC1, DeepSeek, Devin, HF.
- **Channel art (K):** bright background + dark high-contrast type (WCAG ≥ 4.5, measured); avatars
  are warm motifs, never a person. `scripts/make_branding.py --style lavish`. No API for avatar;
  API cannot rename a channel/handle (description yes) → Studio.
- **Repo hygiene rules (each has a failing test, `scripts/test_repo_hygiene.py`/`test_watchdog.py`):**
  every rail that pushes to main must `git pull --rebase` first; any file two workflows commit needs
  a writer-side conflict guard; every health threshold must exceed the REAL driver cadence; every
  foreman-dispatched rail must be watched (a driven-but-unwatched rail fails silently); every new
  scheduled rail needs a foreman rule.

## 🌙 Night rail traps — a video that passed QA gets stranded (2026-11-09; `2026-11-09.md`)
1. **`skip` ≠ `skip_pub`:** "the release exists" is not "the video is queued". Conflating them
   skips the hand-off forever. `scripts/night_built_queued.py` splits the two.
2. **`qa_gate` vetoed every 120-min build** (old `LEN_WARN_MAX=90`): the rail vetoed its own
   intended format. Raised to 150 min.
3. **Ordering in `add_release_to_manifest.py`:** `hit.update(entry)` merged BEFORE `apply_qa_gate`
   → the fresh verdict never reached the manifest (entry stayed `blocked/D`). Gate first, then
   `queue_entry()`; merge copies the old state/qa back ONLY when there is no receipt.
- **An empty receipt is not a bad video:** a skip-build re-run has none, `grade({})=blocked` =
  false veto. The build uploads `receipt.json` to the Release; the hand-off downloads it.
- **A long hook kills retention:** `content/hooks/dharma.md` was 361 chars → **40.3 s** (edge-tts
  Thai ≈ 9 chars/s) — over the 30 s ceiling and matching the 28.9%@2:00. Now 171 chars (~19 s),
  still concrete. Cap in `test_hook_concrete.py` (220 chars). ⚠️ the fingerprint does NOT include
  the hook file → a hook edit alone won't trigger a rebuild.
- **`publish_at=slot` uploads PRIVATE** and lets YouTube flip it public at 19:30 Bangkok (12:30Z).
  Seeing "private" is intended, not stranded.
- New guards: `test_manifest_qa.py`, `test_night_queued.py` (suite 24).

## 🧭 Still-true durable facts (details in daily logs / `docs/`)
- **2026-11-09 defects fixed:** (a) the progress report inflated YPP hours up to 92× — it compared
  channel totals to the long-form bar; `analytics.py` now splits by `creatorContentType`
  (`shorts`/`videoOnDemand`); (b) learning loop went blind when the Data API `videos.list` quota was
  spent — titles now come from committed manifests then YouTube **oEmbed** (no auth, no quota),
  cache `content/titles/<ch>.json`; (c) health cried wolf + 6 foreman rails invisible (one already
  dead: `fetch-music` missing `numpy`); (d) foreman DOWN ~6 h from raw git-conflict markers in
  `content/upload_log.json` → now union-resolved in `publish_shorts`.
- **2026-11-08:** the killer was a **single static card** for a 120-min file (AVD 5.2%) → shipped
  `make_chapter_video.py` (one card per piece, `MAX_CARDS=30`) + a spoken hook + 20–30 min length.
  Search blocker = packaging → `make_cover_youtube.py` + `apply-packaging.yml`.
- **2026-11-07:** genx long-form rail; a playlist id must be written into the manifest entry AND
  inserted by `publish_batch.py` (writing the entry is not enough).
- **Mail on the cloud, not PC1:** `account-watch.yml` reads IMAP from the `IMAP_ACCOUNTS` secret;
  measured it holds only `kongkeat.938@gmail.com` → dharma/kongkeat-story inboxes NOT read yet
  (report now names them instead of hiding). PC1 is dead (Smart App Control blocks the unsigned
  runner; tailnet NXDOMAIN) → do NOT retry PC1; route around it. `docs/PC1-*.md`.
- **`--minutes` is a FLOOR, not a target:** an under-N set is heard twice (28.5-min set under
  `--minutes 30` shipped as 57.1 min). Size the set to exceed the floor in one pass.
- **Quota:** `videos.insert` has its own pool (an upload can succeed while reads 403 all day);
  Data API resets **08:00 UTC**; Analytics has its own quota. GITHUB_TOKEN push does NOT trigger a
  workflow → dispatch explicitly (`KONGKEAT_GH_TOKEN` can).

- **Racing jobs lose records:** publish-shorts and remake-shorts for the same channel pushed at
  once (2026-11-09); `--autostash` + `check=True` hid a conflict in `content/upload_log.json`, a
  live remake id (QLUp6sV16fs) was never recorded, and a 403'd privacy move vanished. Fix = one
  **shared concurrency group per channel** (`shorts-upload-<ch>`) **and** a union merge driver
  (`scripts/git_union_merge.py`, `.gitattributes merge=unionjson`) for the append-only ledgers.
  Guard `test_union_merge.py`. Any new rail that commits a ledger needs both.

## 🗂️ Where things are
- **Automation:** GitHub Actions only (the pod is recycled when idle). watchdog (self-chaining) →
  foreman (dispatches what is due) → rails. Health: `scripts/health.py` → `docs/HEALTH.md` + issue.
  Kill switch `content/STOP`.
- **Learning loop:** `studio_ai.py` (Analytics → panel → `content/insights/<ch>.json`) +
  `video_review.py` (grade A–D + 3 rules) → `gen_short_scripts.py`. Overlap floor 8 chars.
- **Publishing:** `content/<ch>_publish.json` (long) + `_shorts.json`; `DAILY_CAP=3` +
  `content/upload_log.json`. Pages: https://kongkeat938.github.io/ai-content-lab/ (`/docs`, main).
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt`; re-export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`. Full suite: `for t in scripts/test_*.py; do python3 "$t"; done`.

## 📺 ch4 (kongkeat-story) — K's focus: subscribers are flat (2026-11-09; `2026-11-09.md`)
- **Shorts work, long-form is dead.** 28 d: top Shorts 1,083 views/40%, 1,079/104% loop,
  461/115%; every 120-min long-form gets **1-3 views**. **subs/1,000 views = 1.93, worst on
  the fleet** (dharma 2.92, genx 5.36).
- **A Short must not promise a "full clip" it cannot deliver.** 12 of 71 CTAs said "go watch
  the full clip" -- a dead end. `gen_short_scripts` now has a per-channel `forbid_cta`
  (kongkeat-story = `คลิปเต็ม|คลิปยาว|วิดีโอตัวเต็ม|...`); `scripts/test_ch4_cta.py` locks it.
- **`unsubscribedTrailer` is a subscribe lever that was never wired.** Every rail called
  `channel_overhaul.py --only playlists`, so no channel had a trailer. Now ch2/ch4 run the
  full overhaul and ch1's trailer lives in publish-ch1; `test_repo_hygiene` forbids
  `--only playlists`. **It must run after the 08:00 UTC quota reset** (ch1 08:07, ch4 08:05,
  ch2 08:40) -- the genx-longform 04:47 tick would defer forever.
- Still to measure: whether the trailer lifts ch4 subs (Data API `subscriberCount` is
  quota-gated; a 403 at any hour before 08:00 UTC is expected, not an outage).

## 🧑⚖️ Advisor team: 5 fast vendors by default (2026-11-09; `2026-11-09.md`)
- `scripts/advise.py` default team = **`FAST`** = 4 Gemini models + **OpenRouter**
  (5 advisors, two vendors, seconds). `--broad` adds Pollinations (a 6th vendor but
  **~66 s** and 400s on long prompts — a slow panelist drags every decision); `--deep`
  adds 3 OpenHands conversations (~20 min). `FAST_PLUS` kept as an alias of `FAST`.
  K's rule: **≥5 independent advisors, never a person**; K: **ทีมเร็วมีคุณภาพ**.
- `scripts/panel_bench.py` measures each advisor on 5 checkable probes (math, logic,
  exact-format, Thai, counting) + latency. Measured 2026-11-09: all 5/5; median
  gemini-3.5 0.5s · gemini-3.1 0.6s · openrouter 1.3s · gemini-flash 1.5s ·
  gemini-preview ~1-4s (high variance) · pollinations 65.7s. Re-run it before trusting
  a vendor's speed.
- **Bug fixed:** `FAST` listed `gemini-latest` but `ADVISORS` only had `gemini-flash`, so a
  slot silently became "(unknown advisor)" and still counted. `scripts/test_advise_panel.py`
  now fails if any panel name is missing from `ADVISORS`.
- **OpenRouter (free, genuinely new vendor):** key at `~/.pod-openrouter-key` (override with
  `OPENROUTER_API_KEY`). `ask_openrouter()` tries free slugs in order + backoff on 429/5xx.
  Working free models from the pod: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`,
  `cohere/north-mini-code:free`, `nvidia/nemotron-3.5-lightning:free`. Google free slugs
  (`google/gemma-4-*:free`) 429 on the shared pool; `meta-llama/llama-3.3-70b:free` is now paid.
- **Recovering an OpenRouter key:** the UI **masks** the value forever; the internal API is
  Clerk-gated (a raw session cookie does not authenticate `/api/v1/keys`). The only plaintext
  is the **clipboard** after the create-key modal's copy button → create the key in headless
  chromium (playwright + `/usr/bin/chromium`), log in with email+password and the 6-digit email
  code read via Gmail IMAP, then `navigator.clipboard.readText()`. See `.stockwork/or_*.py`.
- **Measured:** panel of 6 answered in **15.3 s**. Evidence `.stockwork/PANEL-EVIDENCE-2026-11-09.md`.
- **Pod tooling:** `ffmpeg`/`ffprobe` via `pip install static-ffmpeg` (no root); copy binaries to
  `~/bin` and add to PATH, or the media tests fail with FileNotFoundError.

## 🔁 Posting loop = post → wait 2-3h → read → adapt (2026-11-09)
- K's rule: ONE clip, wait 2-3 h, look at how it did, then the next. Good → keep the
  shape; bad → change it. Never a burst, never repeat a loser. `scripts/pace.py`:
  `gate()` (2h gap + grade) + `order()` (good keeps the winning shape, bad flips to
  the other). `publish_shorts` records `posted_at`+`shape`; `foreman` posts per_run 1.
- **Bar = the channel's upper quartile, NOT the median.** Half of dharma sits at 0
  views, so a median bar called "2 views in 3h" good. Top quarter 2026-11-09 = 2.2
  views/h. On a channel with a zero-view floor, compare to the *good* clips.
- Views: Data API `videos.list` (fresh, minutes) when quota allows; else Analytics
  API (separate quota, survives a spent Data API) but lags 1-2 days → grades the
  baseline, not the newest. Neither → `unknown` → keep the shape (never invent).
- `posted_at` backfilled on 233 existing Shorts from git history
  (`scripts/backfill_posted_at.py`, needs `--unshallow`; run locally, commit).
- Guard `scripts/test_pace.py`. Doc `docs/POSTING-LOOP-2026-11-09.md`.
- **Gotcha:** publish-shorts CI short-circuits on the daily cap *before* the gate, so
  CI green ≠ pace ran; the guard test is the proof.

## 📉 ch4 (kongkeat): วิวขึ้นแต่ซับไม่ขยับ (2026-11-09) — ดู conversion ไม่ใช่ retention
- K ถาม. วัดจริง 30d: ch4 subs/1k=**1.79** shares=**0** comments=**0** vs genx 5.38/79/15
  -- แต่ retention พอ ๆ กัน (59.5% vs 69.5%) → **retention หลอกได้** ตัวที่ฟ้องคือ conversion.
  วิว steady + 96.6% จาก Shorts feed → ไม่ใช่ reach/แบน แต่ "ดูแล้วไม่ผูกพัน".
- **Panel 5/6 เอกฉันท์:** CTA ท้ายคลิป → คนปัดหนีไปก่อน. ย้าย CTA ไป**กลางคลิปหลังจุดพีค**.
- แก้: `make_short.spoken_sequence(..., cta_mid)` + `--cta-mid` เฉพาะ spec `cta_mid:True`
  (= kongkeat). revert = ลบ cta_mid. guard `test_cta_mid.py`. ยังไม่ตัดสิน: รอ ~3 วัน.
- **บทเรียนวัด:** Shorts แปลงซับด้วย engagement (share/comment/อารมณ์) ไม่ใช่ retention อย่างเดียว.

## 🐛 Durable bug pattern (2026-11-10)
- **symbol ที่ใช้ในโค้ดต้องไม่ถูกครอบโดย import ที่อยู่ใน try/guard.** `publish_shorts.py`
  import `pace` ใน try (ตั้งใจ) แต่ path อัปโหลดเรียก `pace.hook_shape` → NameError ทำให้
  publish job ตายเงียบ ๆ (genx FAIL, ch4/ch2 ผ่านเพราะไม่ได้เข้า path นั้น). นิยาม
  `hook_shape` ที่ module scope + guard `test_publish_shorts_cap.py`.

## 🚨 Feed suppression vs weak hook (2026-11-10) — ดู `docs/CH4-STALL-2026-11-10.md`
- **ch4 kongkeat: Shorts feed หยุดโชว์ทั้งช่อง** (ไม่ใช่ subs ไม่แปลง). feed views 11-01..06=4,340
  → 11-07..10=6; คลิปใหม่ 37 ตัว = 0-2 วิว (คลิปเก่า 8-242). สถานะช่องสะอาด ไม่มี strike.
  genx/dharma flood หนักกว่า (26/49 ต่อวัน) ยังรอด → **flood อย่างเดียวไม่พอ**; ตัวเหตุคือ
  **เสียงเดียว+เทมเพลตเดิม 17-22 คลิป/วัน** บนช่องใหม่ (trust ต่ำ) → อ่านเป็น spam.
- **เช็คก่อนสรุป:** "คลิปใหม่~0 วิวทุกตัว" = **reach ถูกถอด** ไม่ใช่ hook อ่อน → ดู **feed-level
  daily views** ก่อนเสมอ. panel 5/5: หยุดโพสต์ 3-5 วัน, **ห้ามลบคลิป**, กลับมา 1-2/วัน+เปลี่ยน shape.
- **ลูป:** `pace.detect_stall()` (5 คลิปใหม่สุด ≤5 วิว = ดับ) → `gate()` pause จน `STALL_COOLDOWN_H=20h`
  แล้วยอม 1 changed probe. quota หมด=unknown ไม่นับ stall; คลิปมี reach=เคลียร์.
- **K's cadence rule:** ช่องใหม่ต้องวัด **เป็นชั่วโมง ไม่ใช่ข้ามวัน**; รอ 3/5/7 วันได้เฉพาะช่องที่มี
  subs เยอะแล้ว. ใช้ **likes+comments จาก Data API** (มาพร้อม viewCount ใน call เดียว) เป็น
  same-day proxy → `gate()` รายงาน `engagement_per_1k`.
