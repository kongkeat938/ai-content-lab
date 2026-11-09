# Project Memory — ak (ai-content-lab)

**Agent name `ak`** (renamed from AX by K, 2026-10-31). Owner **K**; answers in Thai, wants
**measured evidence, not claims**. ak holds K's grant to administer + decide; still asks K
before publishing to a new channel, deleting history, or renaming.

**This file is a small INDEX.** The loader injects it every session and truncates the tail, so
it must stay short. Full detail lives in `.openhands/memory/2026-11-DD.md` (daily logs),
`.openhands/memory/ARCHIVE-MEMORY-2026-11-09.md` (the old 75 KB index), and `docs/`.

## 🎯 WHAT ACTUALLY GATES THE BUSINESS (measured 2026-11-09; `docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY.** Shorts never count toward the 4,000-h bar. Steer by
  **long-form watch-hours/week + `retention@2min`**, never by raw views (a Shorts-heavy channel
  looked 92× closer than it was).
- **The constraint is the first 2 minutes, not upload volume.** dharma's 120-min file keeps
  102% at 1% of the file (~1.2 min) then **28.9% at 2% (~2.4 min)** — 71% leave. Uploads use
  ~2.8 h/day of a 6-8-clip capacity, so more volume is noise.
- **The Shorts→long-form funnel is dead:** genx 27,014 Shorts views → **2** long-form views;
  dharma long-form views come from **subscribers**, not Shorts. A playlist link in the tail does
  nothing. **Concentrate on dharma** (96% of all long-form watch time); genx/ch4 long-form wait.
- **Winning content is specific + actionable** ("นอนไม่หลับ? ลองทำท่านี้ 10 วินาที"), not abstract
  reassurance. The dharma hook now opens with a concrete action; guard `scripts/test_hook_concrete.py`.
- **Review the decision 2026-11-16** (after ~2 new long-form uploads).
- **Two durable rules learned 2026-11-09:** (a) a guard that checks "health threshold vs driver
  cadence" must **sweep every foreman gate**, not hardcode rails — hardcoding let the same
  false-alarm bug live in `link-shorts`/`set-thumbnails` (issue #20); (b) a generator that can
  drop a piece must **fail**, not write a partial set (a partial night set shipped with no
  `01_open`, the lever itself, and would have been looped twice under the `--minutes` floor).

## 🟠 2026-11-09 — the TRACKING system was lying (defects fixed; `docs/STATUS-2026-11-09.md`)
0. **The progress report inflated YPP watch-hours up to 92×.** `progress.py` compared a
   **channel-level** total against YPP's 4,000-h bar, which counts **long-form only** (Shorts have
   a separate path — 10M views/90 days — and their watch time does not count). Measured 28 d:
   genx **1.3 h** long-form vs **120.2 h** mixed (report said 39% of the bar; truth **0.4%**);
   total 46.2 vs 219.9. **Fix:** `analytics.py` splits by `creatorContentType` (values are
   lowercase **`shorts` / `videoOnDemand`**) → `longform_watch_hours`; `progress.py` reports
   long-form + a `retention@2min` column. Guard `scripts/test_progress_honesty.py`.
1. **Learning loop blind on a spent Data API quota.** `studio_ai.py` + `video_review.py` read
   Analytics (own quota, works) but fetch titles from Data API `videos.list`, which **403s most
   days** → fell back to `"(title unavailable)"`. Measured: every winner on all 3 channels
   untitled → panel returned generic filler → `gen_short_scripts.py` made it into content.
   **Fix:** titles come from the committed manifests (`content/<ch>_shorts.json` + `_publish.json`).
   Guard `scripts/test_learning_titles.py`.
2. **Health alert cried wolf** → 11 issues (#7–#18) in 2 days. `EXPECTED["foreman"]=90 min` but
   the chain ticks the foreman **every 2 h**; `set-thumbnails` 90 min vs the foreman's own
   **180-min** gate. **Fix:** thresholds vs the REAL driver (foreman 240, set-thumbnails 240).
3. **6 foreman-driven rails were invisible to health** — one already dead: **`fetch music`
   failing a day** (`ModuleNotFoundError: numpy`; workflow installed ffmpeg but not
   `requirements.txt`). **Fix:** deps installed; 6 rails added to `health.EXPECTED`; runs looked
   up by **numeric workflow id** (display name ≠ file name, e.g. `"fetch music"` vs
   `fetch-music.yml`, 404'd and blanked the report).
- **Guards** in `scripts/test_watchdog.py`: every health threshold must exceed the real driver
  cadence; every foreman-dispatched rail must be watched (condition-gated ones exempt). Both
  verified to FAIL on revert. **Rule: a rail the foreman drives but health ignores fails silently.**
- **4th (while proving #3): `fetch-music` pushed without `git pull --rebase`** — the only such
  workflow of 20, so it raced the foreman's push. `test_repo_hygiene.py` now also fails any
  workflow that pushes without rebasing. **Rule: every rail that pushes to main must rebase first.**
- **Title sources (order):** live Data API → committed manifests → **YouTube oEmbed** (no auth, no
  quota) → cache `content/titles/<ch>.json` (one writer per channel). oEmbed recovered 7 legacy
  dharma titles no manifest knew.
- **Measured win:** watch-hours 28d **79.12 → 219.87 h** (genx 120.2 · dharma 79.8 · kongkeat 19.9).

## 🖥️ PC1 — mail already moved to the cloud; do not retry PC1 (2026-11-09)
- **Mail is read on the cloud, not PC1.** `account-watch.yml` (ubuntu-latest) reads IMAP from the
  `IMAP_ACCOUNTS` repo secret; `mail_watch.py` is pure IMAP + Data API, **no PC1 path at all**.
  **BUT (measured 2026-11-09): the secret holds only `kongkeat.938@gmail.com`** → dharma
  (`farmmer.938`) and kongkeat-story (`kongkeat.p3`) inboxes are **NOT read yet**. The report now
  says `NOT read <addr>: no app password in IMAP_ACCOUNTS` instead of hiding it. **To cover them,
  add their app passwords to the secret** (`kongkeat.938:pw` per line). *Corrected an earlier
  memory entry that wrongly said all three were read.*
- **If K cannot reach PC1: do NOT retry PC1 channels.** Everything load-bearing runs on GitHub
  Actions. PC1 is optional. Route around it. Historical detail: `docs/PC1-*.md`.
- Root cause PC1 was never drivable: runner `Runner.Listener.exe` is unsigned and **Smart App
  Control blocks it (no allowlist; disabling SAC is irreversible)**; tailnet funnel = **NXDOMAIN**;
  pod = HTTPS egress only. The signed-PowerShell bridge `ops/pc1_agent_bridge.ps1` still needs a
  human at PC1 once → moot while K is locked out. Studio-only jobs (impressions/CTR/revenue) need a
  browser but are **not the YPP constraint**, so they stay parked.
- **Traps in `ops/check_pc1.py`:** `app.all-hands.dev/mcp/mcp` is OpenHands' OWN MCP, not a PC1
  route. `pc1-task.yml` lives in **ax-workspace**, not aeris-drive-automation.

## 🔴 2026-11-09 — foreman was DOWN ~6 h (committed git conflict)
`content/upload_log.json` held raw conflict markers from `git pull --rebase --autostash` in
`publish_shorts.commit()` → every foreman run 19:35Z→01:36Z died on `JSONDecodeError`; no rail
driven from the chain for ~6 h. Fixed: union the ledger, plain `--rebase` (no autostash),
`_union_resolve_upload_log()`, `scripts/test_repo_hygiene.py` (fails on any line-start conflict
marker or unparsable JSON; in `selftest.yml`). **Rule: any file two workflows commit concurrently
needs a writer-side conflict guard.** Detail: `.openhands/memory/2026-11-09.md`.

## ⭐ 2026-11-08 — AVD fix shipped (long-form was ONE card looping; live `3HCOe1jZj2c`)
Root cause (measured): a 120-min dharma file's `averageViewDuration` = **379 s = 5.2%** — the
whole file was **one static card** (`make_night_video.py`). Panel verdict by ROI: spoken **hook**
first ~20 s · cut to **20–30 min** · **change the picture per chapter** · never 8–10 h loops
(Reused Content trap). Shipped `scripts/make_chapter_video.py` (one Ken Burns card per piece,
`MAX_CARDS=30`), `--hook`/`--chapters` in `make_compilation`/`build_night`; wired into genx/ch4/
dharma. Test `scripts/test_chapter_video.py`. **AVD lift NOT yet measured** — baseline 5.2%.
**Lesson: a static picture is what kills AVD; per-chapter pictures are the cheap fix.**

## ⭐ 2026-11-08 — Packaging rail for ch2 (`docs/PACKAGING-PLAN-2026-11-08.md`)
Search blocker = **packaging, not reach**. `scripts/make_cover_youtube.py` (glowing gold Buddha
+ navy night + big Thai type; `_gild()`), `content/ch2_packaging.json` +
`scripts/apply_packaging.py` + `apply-packaging.yml` (title+tags+cover, ledger
`content/packaging_changes.json`). Playlists via `channel_overhaul.py`. `publish_batch.py
--publish-at ISO` holds a video private and flips it at publishAt. ⚠️ first-run CI bugs: `git add
<new-file>` aborts if the ledger does not exist (use `git add -A content/`); re-rendering covers
in CI uses a different Pillow than the build → upload the committed JPG.
⚠️ `scripts/test_watchdog.py` fails any workflow with a `schedule:` that the foreman does not
dispatch. **New rails MUST get a foreman rule.**

## ⭐ 2026-11-07 — genx long-form rail (`docs/PANEL-2026-11-07-CONSENSUS.md`)
genx had 52 Shorts + top Shorts reach but **zero long-form** → every Short funnelled to an empty
playlist. Built `gen_philosophy_scripts.py`, `genx-longform.yml`, `publish-ch1.yml`,
`content/ch1_publish.json`. **Funnel fix:** `add_release_to_manifest.py` writes the channel's
playlist id into every manifest entry; `publish_batch.py` inserts the upload into that playlist
(writing the entry is not enough). Playlist insert that hits a quota 403 → `playlist_added` flag +
repair pass each tick. Live `l5hkDGVIYXE`.

## ⭐ 2026-11-06 — long-form rail is a closed autopilot; quota + ledger facts
- `add_release_to_manifest.py` + `night-compilation.yml` (runs it after the release, **dispatches
  publish-batch explicitly**). **⛔ a push with the default `GITHUB_TOKEN` does NOT start another
  workflow** (anti-recursion) → dispatch explicitly. **✅ `KONGKEAT_GH_TOKEN` CAN dispatch.**
- **Quota split:** `videos.insert` has its own pool, so an upload can succeed while
  `videos.delete`/reads 403 all day. Data API resets **08:00 UTC**; Analytics has its own quota.
  Queue deletes for **08:12 UTC**. `publish-batch.yml` also fires on **push to
  `content/ch2_publish.json`**.
- **Watch-hours is the metric.** Shorts do NOT count toward YPP. 120-min `F4qFHoVpEyI` = 0.0597
  h/view vs ~0.002 for a Short. History in `docs/watch_hours.json`.

## ⏱️ Long-form rail: `--minutes` is a FLOOR, not a target
`build_night.py --minutes N` loops the whole talk until it reaches N min — an under-N set is heard
**twice** (a 28.5-min set under `--minutes 30` shipped as 57.1 min). Size the set so one pass
already exceeds the floor.

## 🔑 Durable principles (K)
- **PCSEV = Problem → Cause → Solution → Execute → Verify** (2026-11-08; `docs/PCSEV-VERIFY-2026-11-08.md`).
  **Every fix K is shown must be framed in all five steps**, and **Verify must measure live** —
  never from our own committed docs (a doc is just another claim: stale-able, wrong-able).
  Trust order: **live API > real output file (ffprobe/ebur128) > a test that can FAIL > committed
  doc (weakest)**. A doc tells you *where* to measure, not *what the answer is*. Best verify =
  a **counter with an invariant** (lifetime views/subs must not fall, must not sit still) —
  it carries the truth in itself (`scripts/counter_ledger.py`, `docs/counters.jsonl`). K pushed
  this exact point 2026-11-09 when the PC1 answer was given as an answer instead of a PCSEV chain.
- **Everything is an algorithm** (2026-11-07): a wall is a rule not yet read. When a paid tool
  dies, a free one does the job. Two duties: **read the vendor's own rule** before declaring
  anything impossible; **an LLM is not a primary source** (verify against docs or a live
  measurement). The one real boundary: identity/account ownership.
- **"แยกไม่ได้" ≠ "ผิด"** (quota-safe identity): a checker that proves identity via the Data API
  dies silently when the quota is spent and reads as "not ours". Use **per-channel secret =
  identity** (`YT_CH1/2/4_REFRESH_TOKEN`); fallback when the API cannot tell, but abort on a token
  provably another channel. `yt_auth.CHANNEL_ENV` + `env_token_for_channel`;
  `scripts/test_channel_identity.py`.
- **Advisor panel MUST be 3+ vendors** (`scripts/advise.py`). Reachable: **Gemini** free API
  (`gemini-3.5-flash-lite`), **Pollinations** text (model=openai), **OpenHands Cloud**
  (`KONGKEAT_OH_KEY`, leave `llm_model` default). Do NOT retry: ChatGPT/PC1, DeepSeek, Devin, HF.
- **Channel art (K):** always a **bright** background + dark high-contrast type (WCAG ≥ 4.5,
  measured); avatars are warm motifs, never a person. `scripts/make_branding.py --style lavish`;
  banner via `set_channel_art.py`; **no API for the avatar** (Studio only). API cannot rename a
  channel/handle (`localizations.th_TH` description works, title does not) → Studio; handle
  2×/14 days.

## 🗂️ Where things are
- **Automation:** GitHub Actions only (the pod is recycled ~20 min idle; nothing in it is
  load-bearing). watchdog (self-chaining timer) → foreman (dispatches what is due) → rails.
  Health: `scripts/health.py` → `docs/HEALTH.md` + a GitHub issue. Kill switch `content/STOP`.
  `scripts/test_watchdog.py` guards the chain + foreman reachability + health coverage.
- **Learning loop:** `studio_ai.py` (Analytics → panel → `content/insights/<ch>.json`) +
  `video_review.py` (grade A–D + 3 rules → `content/insights/`) → `gen_short_scripts.py` reads
  `content/insights/<ch>.json` (`topics` + `rules`). Overlap floor 8 chars for learned topics.
- **Publishing:** `content/<ch>_publish.json` (long) + `content/<ch>_shorts.json` (Shorts);
  `DAILY_CAP=3` + `content/upload_log.json` ledger. Pages:
  https://kongkeat938.github.io/ai-content-lab/ (source `/docs`, branch main).
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt` each
  session; `gh` needs `GH_TOKEN` re-exported (`KONGKEAT_GH_TOKEN`). Full test suite:
  `for t in scripts/test_*.py; do python3 "$t"; done`.

## 🌙 Night rail: 3 traps ที่ทำให้คลิปที่ผ่านแล้ว "ค้าง" (2026-11-09) — รายละเอียด `2026-11-09.md`
night-compilation สร้าง 120 นาที 89 นาที CI → เจอ push race + กับดัก cascade. **3 trap:**
1. **skip ผูกกับ "release มีแล้ว" ≠ "คิวแล้ว"** → รอบหน้า skip hand-off ถาวร. แยก `skip` (build)
   กับ `skip_pub` (hand-off) ใน `scripts/night_built_queued.py`. hand-off รันเมื่อยังไม่ถูกคิว.
2. **`qa_gate` veto ทุกไฟล์ 120 นาที** (LEN_WARN_MAX เดิม 90) — rail veto ตัวเอง. แก้เป็น 150.
3. **ordering ใน `add_release_to_manifest.py`:** merge (`hit.update`) **ก่อน** `apply_qa_gate` →
   verdict ใหม่ไม่ถึง manifest (entry ยัง `blocked/D`). **ต้อง gate ก่อน แล้ว merge**; merge คัดลอก
   state/qa เก่ากลับ **เฉพาะเมื่อไม่มี receipt** (รอบ skip) เท่านั้น.
- **receipt ว่าง ≠ คลิปแย่:** skip-build re-run ไม่มี receipt, `grade({})`=blocked (verdict None)
  → veto ปลอม. build อัป `receipt.json` ขึ้น release; hand-off `gh release download` มากรอก.
- **hook ยาว = ตัวการ retention:** `content/hooks/dharma.md` 361 ตัว → พูด **40.3 วิ** (edge-tts
  ไทย ~9 ตัว/วิ) เกินเพดาน 30 วิ + ตรง retention 28.9%@2:00. เขียนใหม่ 171 ตัว (~19 วิ) ยัง concrete.
  `test_hook_concrete` cap 220 ตัว; fingerprint **ไม่รวม hook** → แก้ hook ไม่ trigger rebuild.
- **hand-off = `publish_at=slot`** → อัป **private** + publishAt ให้ YouTube เปิด public เอง
  19:30 Bangkok (12:30Z). ถ้าเห็น "private" อย่าตกใจ = ตั้งใจ (ไม่ใช่ค้าง).
- เทสต์: `test_manifest_qa.py`, `test_night_queued.py`. suite 24.
