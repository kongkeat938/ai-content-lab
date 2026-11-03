# Project Memory — ak (ai-content-lab)

**Agent name: `ak`** (renamed from AX by K, 2026-10-31). Owner **K**; Thai answers, measured
evidence. This file is an **index** and must stay small — the loader injects it every session
and **truncates the tail**, which is why the old 48 KB file lost its newest work. Detail lives
in `topics/*.md` and the daily logs.

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

## Standing rules
- **AUDIO FIRST**; never claim to have watched/heard — measured numbers only.
- **ak does not upload** — K reviews the first work of each channel.
- **Do NOT invent stories** — build from K's own material in `C:\ax-work\library\<channel>\`.
- A uniform failure = a broken measurement; a scattered one = a real defect.

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
