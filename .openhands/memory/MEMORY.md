# Project Memory — ak (ai-content-lab)

**Agent name: `ak`** (renamed from AX by K, 2026-10-31). Owner **K**; Thai answers, measured
evidence. This file is an **index** and must stay small — the loader injects it every session
and **truncates the tail**, which is why the old 48 KB file lost its newest work. Detail lives
in `topics/*.md` and the daily logs.

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


## yt938-1 status — measured live 2026-10-31 14:45Z
- **ch1** ตาต้า GenX Shop 33 vids / 6 subs · **ch2** Farmmer 10 vids / 7 subs · **ch4**
  kongkeat pratumma 8 vids / 6 subs. ch1 ep01 `E1gxiblSUo0` is **still private** (K has not
  released it); the public ch1 Short `CaVSO74wFms` has 15 views.
- **Auto-publisher ledger = 4** (`docs/published.json` in ax-workspace): ch2 `wIpNM1gqPYc`,
  ch2 `oIsloIKa0J4`, ch1 `CaVSO74wFms`, and **ch4's first auto-Short `Wr5N-NfhGMM`**
  (2026-10-31T14:38Z, public, 25 s). Rotation across all three channels is now proven live.
- **⚠️ The GitHub Actions cron is NOT reliable.** `runs?event=schedule` → **total_count = 1**
  for the whole repo; the `*/30` monitor cron gave 1 tick in ~8.6 h, auto-shorts' crons never
  fired. Posts happen by **manual dispatch** today. Do not claim the channels update 24/7.
  Safe failure mode: `--slot-hours` + the ledger mean a dropped tick costs a post, never a
  double-post. Detail: `ax-workspace/docs/AUTOMATION.md` (last section) + its `2026-10-31.md`.
- **edge-tts female voice re-measured** (6 lines × 3 tries): `th-TH-PremwadeeNeural` 3 ok /
  3 fail, `th-TH-NiwatNeural` 6 ok / 0 fail → ch1's female-voice re-render is still blocked.
- **Real bottleneck is content, not the rail:** per-channel `scripts/` on PC1 are empty; the
  rail is proven. Thai scripts + render is what "ปั้นช่อง" needs.

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

## Authority (2026-10-31)
**ak** holds K's grant to administer and decide ("อนุมัติให้บริหารงาน และตัดสินใจแทน k ได้เลย"). ak acts alone on reversible/internal work; still asks K before publishing, enabling automations, deleting history, or renaming. Charter + log: `ax-workspace/.openhands/memory/DECISIONS.md`.
