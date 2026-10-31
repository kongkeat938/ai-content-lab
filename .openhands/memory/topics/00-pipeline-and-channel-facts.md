## 🚨 READ FIRST — AX runs THREE channels; ch4 = kongkeat pratumma (2026-10-31)
K's correction, verified via YouTube API. **Do not confuse ch4 with `@aerisanime`.**
- **ch1 `@tatagenxgeny`** `UCI6EfsgM1HNjrYarvigxyrQ` · **ch2 `@farmmer-n9t`** `UCM3QO5L_pmj34n1JVlbhh-w`
- **ch3 `@aerismusicth`** `UCm44BjAn03ruOF-WaA3ZRww` · **CANCELLED 2026-10-30** — K handed it to kongkeat938; AX does NOT build/QC/upload/cut Shorts for it.
- **ch4 `@kongkeatpratumma`** `UC7gCIu4G_7QCEJ8hJ-34zoQ` · account **kongkeat.p3@gmail.com** · env `YT_CH4_REFRESH_TOKEN`. This is the channel the ch4 token actually controls.
- **`@aerisanime` (`UCR2AQNtI2o_rxQIEkQeTk9Q`) is NOT ch4** — different channel: created 2021-11-05, 263 English anime fan-edits, 10.5k subs, **no AX token controls it**. Rename cannot change a channel id; the two were created 5 years apart. The 2026-10-24 spec that set ch4=@aerisanime was wrong.
- **Canonical registry = `ops/ax_channels.json` in ax-workspace** (root `ax_channels.json` is a deprecated mirror). `ops/ax_channels.py emit-content-lab` regenerates `channels.json` here. All copies now agree; `_superseded` records both old mistakes.
- **Emitter bug fixed:** `content_lab_channels()` hardcoded `status: "live..."` and erased the CANCELLED flag. A generated file must not hardcode a field the source carries.
- **AX ดูแลปั้น 3 ช่อง: ch1, ch2, ch4.**
## Competitor strategy + the quality gate (2026-10-30)
- **This repo (`ai-content-lab`, story-video) is a *different project* from
  `ax-workspace`/yt938.** It has its own 3 channels in `channels.json`: ch1
  `@tatagenxgeny` (6 subs), ch2 `@Farmmer-n9t` (1 sub), ch4. It is NOT the yt938
  channel set. All three `YT_CH*_REFRESH_TOKEN` env secrets work here with the
  full `youtube` scope.
- **⚠️ ch4 was mislabelled — now resolved (2026-10-30, owner-confirmed).** ch4 IS
  `kongkeat pratumma` (`@kongkeatpratumma`, `UC7gCIu4G_7QCEJ8hJ-34zoQ`, 6 subs,
  8 videos) — the channel `YT_CH4_REFRESH_TOKEN` controls. It is a **Thai
  storytelling channel** (Thai literature + short stories + life-lesson Shorts;
  its 2 Shorts got 882 and 378 views), i.e. the same pipeline as ch2, not a new
  one. `channels.json` now has slug `ch4-story` for it. **`@aerisanime` is a
  DIFFERENT, unrelated channel** (anime edits, 10.5k subs, 263 clips) that no
  token here controls — it is no longer AX's ch4. Verify a channel's identity with
  `channels?mine=true` before producing work for it.
- **`commentThreads` is 403 "insufficient authentication scopes"** even with the
  full `youtube` scope — comments are not readable from these tokens.
- Deliverables: `work/research/COMPETITOR-STRATEGY.md` (measured competitor
  numbers + plan) and `work/research/RUNBOOK.md` (per-episode loop + checklist),
  with tooling `collect.py`/`deep.py`/`measure.py`/`quality_gate.py`/`yt.py`.
  Kept in `work/research/` on purpose — `scripts/` is the pipeline owner's dir.
- **Market lesson, measured (149 ch / 272 vids, TH):** the winner in each niche
  wins on **cadence, not craft**. ch2: `hiphoplanla` uploads 0.4/week yet median
  30.5k (repeatable chants), 43× PURIFILM's 713 (uploads 6.6/wk, 2× the subs).
  ch4: DODI long-form median 304k vs its Shorts 21.7k — **long-form + Shorts
  funnel**. Titles that win: a number (37% of top 40), a `|`, a series number,
  hashtags; no emoji in ch1/ch2.
- `quality_gate.py <ep> --channel chX` checks one finished episode against the
  definition of done, prints measured values, exits 1 on a hard failure; verified
  it catches injected defects (digits, LUFS, peak, missing image/source/attr).
  `measure.py` prints our median views vs the §6 targets.
- **The concat demuxer truncates a still-image slideshow** (found by rebuilding
  ep02, commit `3d21d59`). `make_video.py` used to feed the poster JPEGs to
  `-f concat` with `duration` lines → output 648.9 s vs 662.8 s audio (~14 s
  lost), so the closing line at 658.5 s never played. **Fix: encode each card to
  a clip of its own length, then `-c copy` concat.** Guard: gate check
  `video.matches-audio` (≤1 s apart). `-color_range tv` alone reports `unknown`
  — you also need `-colorspace/-color_primaries/-color_trc bt709`.
- **`work/research/make_short.py`** cuts a vertical 10–59 s Short from a finished
  episode on narration-line boundaries (blur-pad to 1080x1920, burned Thai
  caption) — the funnel the strategy calls for.
## yt938-1 ALL FOUR CHANNELS SHIPPED (2026-10-29)
Long videos, all public: ch1 `3TJp1eWiB4U`, ch2 `lvvGvsZHAp8`, ch3 `avk2HxAumw0`,
ch4 `MBkSa_wG7sk`; 8 shorts. Record: `yt938/output/_audit/uploaded.json`.
The ch3 (song) channel failed QC on four defects, all *geometry between the video
and the song*, none in the song itself (commits da52a35, 75092c5, 66f7c09):
- **video = lead + tail + sum(shot durations)** (xfade overlaps cancel exactly).
  `build_frames` adds `GAP` per still and `render_video` holds LEAD/TAIL -- both
  are for narration's silence. A song has neither, so ch3's video ran 11 s past
  its audio. Song channels pass `gap=lead=tail=0`. When a clip's length looks
  wrong, check this law first.
- **Single-pass `loudnorm` is a dynamic gain; it took -13.9 LUFS to -19.6.**
  Always two-pass (`tts.loudnorm2`) for a master.
- **AAC overshoots a dense stereo mix ~0.7 dB** (-1.48 in -> -0.80 out). Master a
  song at `tp=-2.5`, not -1.5.
- **A colour-count gate must test shape, not presence.** The red-badge gate
  counted red pixels; ch3's screenprint style is red halftone dots, so its title
  frame scored 5454 against a limit of 50 with no badge. A badge is a *solid
  plate* -- count red runs >= 60 px (dots top out at 30). Same rule for any gate
  keyed on a colour the art style itself uses.
- `make_short.py` had no song path (it read `voice/*.mp3` + `narration.wav`), so
  ch3 published zero shorts and the loop swallowed the exit-2. When adding a
  channel *kind*, grep every `ops/` script for what it assumes about that kind.
- **`ops/test_verify_clip.py` fixtures keep pointing at deleted paths and
  shrinking silently** (third time). Derive fixtures from the reference clip's own
  directory, and make each case assert its target gate fired. Detail in
  `2026-10-29.md`.
## What gets views here (measured 2026-10-29) + Shorts
- **Tokens carry only the `youtube` scope -> the Analytics API is 403.** No
  retention/impressions until K re-authorises with `yt-analytics.readonly`. Use
  **`ops/yt_research.py`** instead (search.list order=viewCount, regionCode=TH).
- **Shorts carry discovery; the long clip is the product.** Measured last 60 d TH:
  a childhood-snack **1-min short = 3.0M views**, and 10-19 min long clips 177k-240k
  (ch1's exact format); dharma **short 404k**, 80-116 min bedtime 40k-320k (ch2's);
  แนวคิด/ข้อคิด is the weak one (3k-24k, ch4). Winning channels have tiny subs
  (6.4k subs / 322k views), so subs are not the barrier -- packaging is.
- **`ops/make_short.py`** cuts 45-58 s on narration line boundaries; it must rebuild
  build.py's timeline scale or the cut drifts. Rejects overlapping windows.
  **`ops/publish_shorts.py`** cuts+uploads+links the long clip, idempotent, and is
  wired into `ops/yt_deliver.sh`.
- ch2 image gen is ~50 s/image (~1 h 50 m/episode). A still counter is not a hang --
  check the newest jpg's mtime.
## ⚠️ READ FIRST — org structure + the script-origin correction (2026-10-27)
- **K = ผู้บริหารสูงสุด.** **AX = orchestrator** — does the work and decides on K's
  behalf. Once K approves a channel, AX builds and maintains the automation so it
  runs 24x7. Standing order: **finish the current job before starting the next.**
- **Do NOT invent stories.** The `yt938/specs.py` stories (ch1..ch4) and
  `ch4-anime/scripts/ep1_shots.py` were written by the agent, not supplied by K —
  K caught this. Every clip must be built from **K's own material** in
  `C:\ax-work\library\<channel>\` (mirrored at `I:\My Drive\library\`): the
  `scripts/` narration, the `images/`, the `music/`. For owner-supplied assets use
  **`yt938/make_owner_clip.py`**, not `build.py`.
- K's material also appears in `C:\Users\User\Downloads` (profile is `C:\Users\User`).
- PC1 transfer: use **`curl.exe -X PUT --data-binary`** to
  `https://work-2-.../uploads/<path>`; `Invoke-WebRequest -InFile` hangs. See
  `.openhands/memory/2026-10-27.md`.
## ⭐ PROJECT NAME: `yt938-1` (2026-10-26)
This whole clip-production effort is now named **`yt938-1`** and the owner asked
for the name to be *embedded* in the work. It is stamped in: `PROJECT.json` (repo
root + `ch4-anime/`, `song-video/`, both `output/` dirs), `AGENTS.md` header,
`ch4-anime/README.md`, `song-video/README.md`, the ch4 skill header,
`docs/automation-system.md` §0, and `C:\ax-work\library\PROJECT.txt` on PC1.

**Canonical clip workflow (fixed, 5 steps):** 1) story by a professional writer →
2) Thai voice-drama script by a professional director → 3) narration by a
professional voice actor → 4) music from a **free music tool** (e.g. Google Flow
Music `flowmusic.app`) → 5) stills from a **free AI image tool** (e.g. Gemini),
driven by the director's script. Steps 1-3 are people; 4-5 run on the owner's PC1
(both tools need a logged-in Google browser; sandbox cannot drive them —
flowmusic session URL 307s to `/`, Gemini API 403). Automation covers assembly +
verify. Details: `docs/automation-system.md`, `docs/automation-pipeline.json`.

**Work store:** `C:\ax-work\library`, one dir per channel, subfolders in workflow
order `story/ prompts/ images/ music/ audio/ raw/ ready/ posted/ thumbs/ scripts/`
(+ `CHANNEL.txt`). ch4 arm = `ch4_kongkeatp3`.

**yt938-1 pipeline — built 2026-10-26, one clip per channel (commit `08ce8e7`).**
`yt938/build.py` + `yt938/specs.py`; run `python3 yt938/build.py --channel <name>`
or `--all`. Reuses the proven ch4 modules by import (`compose`, `karaoke`, `tts`)
plus `song-video/scripts/fetch` for CC music. Steps: images → voice → audio →
music (skippable) → frames → karaoke+video; **resumable at every step**. Per-run
record: `output/<episode>/meta.json` (duration, LUFS, music credits, per-step
timings) + `build.log` + `credits.txt`; run-wide `yt938/RUN_REPORT.md`. Clips are
pulled to PC1 by `C:\ax-work\_ax\yt938_sync.ps1` (sha256-verified).
- ch1_tatagenxgeny 52.3s · ch2_farmmer 72.9s · ch3_aerismusic 51.0s (all with a
  ducked CC bed) · ch4_kongkeatp3 59.0s **no music** (channel rule).
- **Images dominate cost: free tier is a hard 1 image / 45 s / IP (~47 s each).**
  10-12 shots = 8-20 min per clip. Plan batches around this.
- Character identity comes from repeating the character paragraph in every prompt
  + a fixed seed; the free tier silently ignores img2img references.
- Review: `bash yt938/serve.sh` → port **12001** (work-2 host). Only 12000/12001
  have public URLs; 12002 has none.
- **Blocker (open):** Chrome's CDP remote-debugging prompt grants "full control
  over this Chrome session... your saved data, cookies and site data" — a
  privilege escalation on the user's profile. Not accepted without explicit
  consent, so Gemini/Flow Music UI automation is unavailable. `GEMINI_API_KEY` on
  PC1 is also a placeholder. Not on the critical path: Pollinations (images) +
  Openverse (CC audio) produce the same asset class without login.

**Where deliveries go on PC1** — Google Drive is mounted as real drive letters.
`Get-CimInstance Win32_LogicalDisk` shows the account in `VolumeName`
(`"<email> - Google Drive"`):

| Drive | Account | Path |
|---|---|---|
| **`I:`** | **farmmer.938@gmail.com** | `I:\My Drive\library` ← the delivery target |
| `G:` | kongkeat.938@gmail.com | `G:\My Drive` |
| `H:` | aerismusic8@gmail.com | `H:\My Drive\AX Content Lab` (old AX lab) |

Clips go to `I:\My Drive\library\<channel>\ready\`; `I:\My Drive\library\index.html`
plays them. `yt938_sync.ps1` does sandbox→local→Drive with re-hash (repo copy at
`yt938/yt938_sync.ps1`). Note the pod can restart mid-session and kill the review
server — a 502 on the pull means the server is down, not the file; re-run
`bash yt938/serve.sh 12001` and retry.
## What this repo is
`/workspace/project` — the AX / AERIS / AKATH working repo. Older workstreams
(song-video, ch4, akath) are superseded by yt938-1; their detail is in
`2026-10-25.md`, and channel state in `yt938/docs/LIMITS-and-plan.md`.
## Thai TTS quality (moved)
Recipe and measurements now live in **`REFERENCE-thai-tts.md`**. The three things
that matter: **text prep dominates** (newlines are the pause mechanism, ~1.1 s each;
never collapse them with a `\s` regex); **spell Thai numbers out** (edge-tts has no
Thai number dictionary); **loudnorm needs two passes** and a hard compressor stage
first, or the true-peak ceiling caps the gain below -14 LUFS.
## ch4-anime image quality (2026-10-26)
Owner rejected the first episodes: **"ภาพไม่สวย"**. The cause turned out to be
the 0.59 MP Pollinations cap plus a `sys.path` bug (see the 2026-10-28 sections
and `REFERENCE-image-generation.md`), not the prompt. Detail in
`REFERENCE-image-generation.md` and `2026-10-26.md`.
## Image-source ceilings (2026-10-28) -- measured, see yt938/docs/LIMITS-and-plan.md
**FLUX.1-merged costs 90 s of GPU per 1088x1920 image.** HF daily quota:
unauthenticated 2 min, free account 5 min, PRO ($9/mo) 40 min -> **1 / 3 / 26
images per day**; a 123-still channel is 123 / 41 / 5 days. Full-res FLUX is
**not reachable free** at any realistic count -- this is the real wall behind
"ภาพไม่สวย", not the prompt. The bucket refills slowly (87 s left stayed flat
for 22 min), not hourly.
**Pollinations `sana` is hard-capped at 0.59 MP** -- asking 1440x2560 still
returns 0.59 MP, ~47-51 s each. Only `sana` works (flux 503, turbo 402, kontext
403). So no free image source beats 0.59 MP today.
Other limits: edge-tts **no observed limit** (3.1 s/line, `th-TH-NiwatNeural`);
Openverse music 20/min, 200/day; YouTube upload 1,600 of 10,000 units/day ->
6 uploads/day; no GPU on the pod (ACE-Step = CPU); 605 MB per build, 14 GB free.
Gemini API 429s on free-tier input tokens; Gemini web locked to Flash-Lite.
**Measure the artifact, not the request** -- a 1440x2560 request that returns
0.59 MP is invisible until you open the file.
