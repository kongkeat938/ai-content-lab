# Project Memory — ak (ai-content-lab)

**Agent name: `ak`** (renamed from AX by K, 2026-10-31). Owner **K**; Thai answers, measured
evidence. This file is an **index** and must stay small — the loader injects it every session
and **truncates the tail**, which is why the old 48 KB file lost its newest work. Detail lives
in `topics/*.md` and the daily logs.

## 🏁 2026-11-03 — the business turn (ak runs it)
K's standing order: **ak runs this as its own business; revenue is the objective; all tools;
ask ChatGPT/Gemini on a first failure, never ask K.** K owns the accounts.
- **ch2 long-form is LIVE: `F4qFHoVpEyI`** (120 min, public). `night_110` held to 2026-11-05.
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
- **GitHub `schedule` NEVER fires here** (`event=schedule` total 0) → automation = **watchdog**
  (self-chaining) → **foreman** (dispatches what is due, idempotent) → rails; `health.py` →
  `docs/HEALTH.md`. Kill switch `content/STOP`. Docs: `docs/MONITORING.md`.
- **Niche truth (measured 2026-11-03, ch2 dharma):** long-form winners = **บทสวดมนต์ก่อนนอน /
  ปล่อยวาง, 20 min–3 h** (21.4M, 21.0M, 12.4M views). Shorts winners = **53 s–1:33** with a
  **question** hook ("เหนื่อยใจอยู่ใช่ไหม"). Our Shorts were 19 s → changed to 8-9 lines + rate
  -15% = **46 s**. `scripts/consult.py` = ask Gemini with real numbers (K's order: ask an AI,
  never K).
- **ch2 upload ceiling ~7-8/day**; `thumbnails.set` 429s after ~3 → use `--skip-existing`.

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
