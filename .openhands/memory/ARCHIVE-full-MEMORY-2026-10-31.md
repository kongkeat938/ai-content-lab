# Project Memory — AX

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

## A local record of a remote fact goes stale — verify before skipping (2026-10-29)
- **`ops/yt_publish.py` skipped any episode in `_audit/uploaded.json`.** That file
  is a *local claim*, not proof. A video deleted on YouTube leaves the record
  saying `"public"` forever, so `yt_deliver` skipped the episode on every tick and
  could never repair it. Found live: **ch4_ep01 `MBkSa_wG7sk` (ch4's only
  long-form clip) is deleted (404)**; 11 of 12 published videos are live. The skip
  is now gated on `recorded_id_is_live()`: `True` skip, `False` re-upload, `None`
  (no token / API error) keep the old skip so a transient failure cannot duplicate.
  Guarded by `ops/test_publish_record.py`.
- General rule: before skipping work because "the record says it is done",
  re-check the remote. Treat "cannot tell" as "keep the old behaviour", never as
  "do the work again". `ops/yt_audit.py` was already correct — the gap was that
  nothing compared its output to the record.

## PC1 is drivable; the C:->D: migration is done (2026-10-29)
- **`ops/check_pc1.py` was reporting FAIL against a healthy PC1.** Its reachability
  check sent an *unauthenticated* GET and read the resulting 401 as "the key
  differs". This server requires auth on every request, so 401 is what an anonymous
  probe always gets. Send `Authorization: Bearer $PC1_MCP_TOKEN` and a real
  `initialize`; only then does a 401 mean the key is wrong. Tier 3 needs the same:
  streamable-http rejects a bare `tools/list` with 400, so `initialize` first and
  reuse the `mcp-session-id` header on the follow-up. Fixed 2026-10-29.
- Registration is per-conversation state, not a file: `POST
  http://localhost:60000/api/settings/mcp/pc1-winremote` with the agent key from
  `/proc/1/environ` (`SESSION_API_KEY`). A conversation loads its tool list once at
  start, so a server restart mid-session makes the `pc1-winremote_*` tools vanish
  ("Unknown tool") until a new conversation -- drive PC1 over raw MCP instead.
- **Windows locks a running process's cwd, and that blocks `Remove-Item -Recurse`.**
  The winremote MCP server had been started with its cwd inside `C:\ax-work\_ax`,
  so the whole tree could not be deleted. Restart the server from `C:\` first
  (`ops/pc1_finish_move.ps1`). The same trap applies to any "directory in use"
  error on Windows: find the holder's cwd before blaming a file lock.
- T6 complete: `C:\ax-work` copied to `D:\ax-work` (8810 files, byte-for-byte
  verified), C: deleted, `C:\ax-work` left as a **junction** to `D:\ax-work`, and
  the library mirrored to `I:\My Drive\library`. All clip work now lives on D:.

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

## ch3's song runs now — ACE-Step is a memory problem, not a speed problem (2026-10-29, commit 9af2346)
The song phase had never once run. Four stacked defects:
1. `build.py` invoked `make_song.py` with **system python**; the `songenv` venv was
   never used -> `ModuleNotFoundError` read as "song generation failed".
2. `uv venv` puts its **interpreter** (`~/.local/share/uv/python`) and cache on
   root, so a pod recycle left `songenv/bin/python` dangling beside 2.3 GB of
   surviving site-packages. **`ops/setup_songenv.sh`** pins `UV_PYTHON_INSTALL_DIR`
   and `UV_CACHE_DIR` under `/workspace`; rebuild is ~1 min. ACE-Step is **not on
   PyPI** (clone `ace-step/ACE-Step` into `work/acestep-repo`), needs Python 3.12,
   and torchvision must come from the **same CPU index** as torch (else CLIP dies
   with `operator torchvision::nms does not exist`).
3. **float32 = 13.2 GB on a 15 GB pod; it killed the sandbox twice.** From the
   safetensors header: transformer **3.31 B params**, stored bf16. `dtype="float32"`
   is the pipeline default; `bfloat16` (now `make_song.py`'s default) loads in ~12 s
   at ~7 GB. Watch RSS with a **watchdog, not `ulimit -v`** -- the cap blocks the
   6.6 GB safetensors mmap and every failure then looks like `MemoryError` inside
   diffusers' swallowed-exception text fallback. Cost: 8 steps/30 s = 90 s;
   **60 steps/240 s ≈ 47 min** (~0.8 s per step per 4 s of audio).
4. `torchaudio.save` on 2.11 delegates to **torchcodec** (absent; its wheel cannot
   load FFmpeg here). `make_song.py` now assigns `pipe.save_wav_file` to a
   soundfile writer, and passes `save_path` as the **exact `song.wav` path** --
   ACE-Step appends a timestamp when handed a directory, so `build.py` never found
   the file. `yt_queue.sh` stamps/logs moved from `/tmp` to `_audit/` for the same
   recycle that they exist to diagnose.
**Rule: for a multi-billion-param model on CPU the question is "does it fit", not
"is it slow" -- read the safetensors header for params and dtype first.**

## Publishing is now duplicate-safe (2026-10-29, commit 27ad04c)
The live ch2 duplicate (`qf3O3zbTT_c` + `G75P01jX0Tc`, same title, 3 min apart)
was three defects, all in the publish path:
1. **`yt_upload.py` set the custom thumbnail AFTER the upload and let a 403 abort
   the script.** A channel without phone verification returns "doesn't have
   permissions to upload and set custom video thumbnails" even though the video
   uploaded fine → non-zero exit → `yt_publish` printed "UPLOAD FAILED" and never
   recorded the id → the 30-min loop re-uploaded. Thumbnail is now best-effort.
   This fired live on ch4 at 16:05 (`9M11eMAjmSU`, then `MBkSa_wG7sk`).
2. **Records were written only after the upload returned, non-atomically.** A
   kill in between (pod restart) leaves a video live but unrecorded → re-upload.
   `yt_publish.py`/`publish_shorts.py` now write `.part` + `os.replace` and, before
   uploading, adopt a live video with the same **title AND duration (±3 s)**.
   Duration matters: ch4 has a 1-min video sharing the 16-min build's title.
3. **`publish_shorts.py` hardcoded the title suffix `วัยเด็ก`** for every channel
   (ch2's live shorts carry it by mistake). Now uses the channel's own primary tag.
**Rule: any upload is "done" only once its id is in `uploaded.json`. A thumbnail
failure must never be fatal, and the record must be written before the next loop
run can start.**

## Image sources: all three can be down at once (2026-10-29)
A *fresh* channel needs live renders; a *rebuilt* one does not — **Pollinations
serves previously-rendered prompts from its CDN cache (~0.4 s each)**, which is why
ch4's 132-still rebuild finished in 60 s. ch3_ep01 had no cached images (not in
git, not on PC1) so it stalled at image 0 while every source was unavailable:
**FLUX ZeroGPU** ("81 s left, try again in 7:11:17"), **Pollinations**
(`FREE_LIMIT` 402 + global 503 "Classic API is at its limit"), **Gemini API**
(`RESOURCE_EXHAUSTED`). Do not assume a rebuild proves the image path works.

## T6 PC1 storage → D: (2026-10-29) — prepared, not run
K wants all clip work on drive `D:`. **PC1 is unreachable from the sandbox again**
(funnel **502** with token / 401 without → backend down; 8090/3389/22 closed; the
agent server's own `/api/mcp/test` also 502). Only a human at the machine can
restart it: `ops/pc1_fix_remote.ps1 -Token <PC1_MCP_TOKEN> -Persist`.
So the move is a tested deliverable, not a done deal: **`tools/pc1_move_to_d.ps1`**
(manifest → robocopy → verify sha256 → *then* delete C: → mirror to
`I:\My Drive\library`; leaves a `C:\ax-work` junction). `-DryRun` first.
Served for PC1 to fetch (identical sha256 to the repo copy):
`https://work-1-aawbtzbmlbinnzlo.prod-runtime.all-hands.dev/pc1_move_to_d.ps1`.
Defaults now `D:\ax-work` in `pc1_setup`/`pc1_push`/`yt938_sync`/`pull_ch2_to_drive`.
- **You can test PowerShell here.** `~/pwsh/pwsh` (install: pwsh linux-x64 tar.gz
  → extract; run with `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`). `tools/test_pc1_move.ps1`
  loads the script's real functions **by AST** and asserts each failure mode —
  including **same-size sha256 corruption**, which a size-only check passes.
- **`Split-Path -Qualifier` THROWS** on a path with no drive letter (UNC/harness);
  read it in a `try`. **robocopy exit 0-7 = success**, only 8+ is failure.

## yt938-1 SHIPPED ch2 + the loops now run unattended (2026-10-29)
- **ch2_ep01 LIVE public: https://youtu.be/lvvGvsZHAp8** (16:06, สะพานใบไม้ที่หายไป)
  + shorts `G75P01jX0Tc`, `FAEKf4FP_Qs`. ch1 was already live (`3TJp1eWiB4U` +
  2 shorts). Both shipped by the loops with no human step.
- **Four loops, all need `setsid nohup ... </dev/null &`** (a bare `&` dies on the
  next terminal reset): `ops/yt_queue.sh` (build ch1->ch2->ch4->ch3 serially, then
  QC), `ops/yt_deliver.sh` (every 30 min: QC-passed -> assets -> public upload ->
  shorts), `ops/yt_pulse.sh` (3-hourly audit+stats), and **`ops/ax_sync.sh`**
  (every 20 min: commit + push, so an empty pod cannot lose the day again).
- **`uploaded.json` is the double-post guard AND the only record of what is live.**
  It is tracked in git now. If it is ever lost, rebuild it from the channels via
  `ops/yt_audit.py` + `videos().list` -- do NOT let the deliver loop run without
  it, or ch1 re-uploads.
- **A stored `verify.json` is a claim about one file at one target length.** A
  debug run left ch2's dir with `"passed": true` for a 73 s stub; the deliver loop
  uploads on that literal string. Check the `duration` gate against the episode's
  `target_s`, or just re-run `ops/verify_clip.py`.
- **`faster_whisper` is required for word-level karaoke.** Without it `wordalign`
  fails per line and the build silently falls back to syllable estimates (still
  passes the gates, but captions are coarser). `pip install faster-whisper`; the
  `small` model caches in ~8 s.
- **Two latent bugs surfaced only when the loop ran the Shorts step** (ch1's shorts
  were uploaded by hand, so the path was never exercised): `publish_shorts.py`
  called `re.search` with no `import re`, and `make_short.py`'s overlap guard read
  `c[2]`/`c[3]` from a `(score, lo, hi, span)` tuple, making it a silent no-op that
  shipped two shorts one line apart. Both fixed; `ops/test_short_overlap.py` now
  fails on the old code. **A guard needs a test that asserts it rejects.**
- Pollinations images can be served from its CDN cache (deterministic
  prompt+seed URL), so a "129 stills in 58 s" run is a cache hit, not a bug.

## yt938-1 SHIPPED ch1 + bed-level lesson (2026-10-28/29)
- **ch1_ep01 LIVE public: https://youtu.be/3TJp1eWiB4U** ("ของเล่นวัยเด็กที่ไม่มีวันหมดอายุ",
  15:40). Uploaded with **no human step** by `ops/yt_deliver.sh` once verify.json said
  passed. Registry: `yt938/output/_audit/uploaded.json`.
- **Never set the music bed with a fixed multiplier.** Free tracks differ by ~9 dB, so
  one gain lands the bed 9 dB down on one episode and *level with the voice* on another
  (ch1 shipped that way, burying the narration). `mix_bed` now measures the real
  headroom with **the verifier's own `bed_level()`** (loaded by path) and re-renders to
  `BED_TARGET_DB` (9.0) under the voice. Sign: head = speech - bed, so correct with
  `gain += (head - target)`; the inverse is positive feedback.
- **verify_clip needs the CLEAN music stem or it false-FAILs.** Without it a correct
  clip scores ~25% vs a 30% gate; with it 69% (music-only 8%). It now auto-discovers
  `<dir>/music/*`, and auto-discovers narration.wav. Duration tolerance is 10% to match
  the builder's own gate; a gap inside the 1.5 s lead-in is not a caption flicker.
- **`ops/remix_bed.py`** swaps only the audio (`-c:v copy`): fix a rendered clip's mix
  in ~2 min, no video re-encode.
- Restore after a pod restart (everything vanishes): `sudo apt-get install -y ffmpeg
  fonts-noto-core fonts-thai-tlwg` + `pip install numpy pillow pythainlp
  google-api-python-client google-auth-oauthlib google-auth-httplib2`. No Thai fonts ->
  `publish_assets.py` dies.
- Loops (all need `setsid nohup ... </dev/null &` or they die on the next reset):
  `ops/yt_queue.sh` (build each channel serially, then QC), `ops/yt_deliver.sh` (QC-passed
  -> assets -> public upload, every 30 min), `ops/yt_pulse.sh` (3-hourly audit+stats).

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

## ⚠️ The pod can come back EMPTY — how to recover (2026-10-29)
Happened twice. `/workspace/project` holds only `.git` (0 commits, **no remote**)
and a stale `MEMORY.md`. The code is NOT gone: the previous conversation's
**sandbox** still holds it. Two sources, both needed:
1. `/tmp/archive.patch` (`git apply --binary`) = the tracked tree, one day stale
   (move `.openhands/memory/MEMORY.md` aside first or apply aborts).
2. The dead session's event archive (`event_*.json`) = the *missing day*. Replay
   its file ops **in event order**: `file_editor` create/str_replace/insert,
   shell heredocs (resolve relative paths against `cd /workspace/project`), and
   re-execute the recorded `python3 - <<'PY'` writers (skip any mentioning
   `git push|urllib|subprocess|rmtree`). `>` truncates, `>>` appends — get this
   wrong and logs come out truncated. Replays are **not idempotent**: reset to
   the archive state and run once.
Then **graft, don't re-root**: `_export/yt938-code.bundle` carries the real
**51-commit** history (tip ee6557e). `git fetch <bundle>
refs/heads/master:refs/heads/from-bundle && git reset --soft from-bundle`, commit.
**Durable push target is `kongkeat938/ax-workspace` (private)** with
`KONGKEAT_GH_TOKEN`; `main` (3109aaf) stays untouched. GitHub rejects >100 MB
files — `ch4-anime/output/*/*.mp4`, `yt938/library/*/ready/*.mp4` and
`song-video/build/*.mp4` are gitignored for that reason.
`kongkeat938/ai-content-lab` is a *different* project (story-video). Full detail
in `2026-10-29.md`.

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

## Key learnings
- The sandbox is ephemeral: on cold start the workspace was empty and no prior state existed anywhere. Persist important state to git (and eventually a remote) to survive restarts.
- Do not assume an integration is connected — probe it (curl / real call) and record the result.
- **`GITHUB_TOKEN` in this sandbox is a GitHub App token with READ-ONLY repo access**
  (`permissions: {admin:false, maintain:false, push:false, triage:false, pull:true}`).
  It cannot create repos (403) and cannot push (403). GitHub account `kongkeat938` (the
  token identity) has 0 repos. **Re-confirmed 2026-10-25 against
  `aerismusic8-alt/aeris-drive-automation`: `git push --dry-run` → 403 "Permission to
  ... denied to kongkeat938".** So clone-and-commit works, push never does. Do not plan
  GitHub push/create work without the user granting access first; commit locally and
  report the blocker instead.
- **YouTube upload pipeline is PARKED** (see above). The OAuth setup, the
  wrong-account hazard and the ~19-videos/day per-account upload cap are documented
  in `PARKED-channels.md` — read that before doing any YouTube work.
- Available MCP tools are only PR-creation (GitHub/GitLab/Bitbucket/Azure) + Tavily search.
  There is no Google/YouTube MCP server.

## Python tooling gotchas (reusable)
- `pip install faster-whisper` upgrades `click` to 8.5, which **breaks gtts**
  (`gtts` requires `click<8.2`). Re-pin `pip install "click<8.2"` afterwards.
- faster-whisper's `decode_audio` passes `metadata_errors=` that the installed
  PyAV rejects (`TypeError: open() got an unexpected keyword argument`). Bypass by
  decoding to f32le PCM with ffmpeg and passing the numpy array to
  `model.transcribe()`. Whisper models are a large download — run in background.
- **Do not force `language="en"` to decide whether audio has lyrics.** On Thai
  narration Whisper *translates* and emits fluent English, which looks exactly
  like detected lyrics. Detect the language first, or transcribe a music-only
  signal.
- **To check whether background music has vocals, test the music file or the
  ambient bed — never the mixed video.** Separating the `vocals` stem from a
  finished video with demucs also captures the narration, so it cannot
  distinguish a clean bed from a dirty one.
- Ephemeral sandbox: `pip install -r requirements-tools.txt` after every restart
  (edge-tts, faster-whisper, demucs + torch). `requirements.txt` alone is not
  enough.

## ffmpeg gotcha (reusable)
Building a still-image video with a music bed: `apad` on the audio makes the stream
infinite, so `-shortest` never fires and the encoder runs forever producing an
unplayable file (`moov atom not found`). Use `amix=duration=longest` +
`atrim=0:{dur}` + an explicit `-t {dur}` instead. For `zoompan`, feed it a
`scale=1600:900` source (not 2560:1440) and use `-preset veryfast` — ~10x faster.
`tremolo`'s `f` parameter minimum is **0.1 Hz** (0.06 → "out of range", exit 222).

- **`loudnorm`'s true-peak figure does not catch AAC overshoot.** It is a *sample
  peak on the PCM*; the encoded AAC overshot to +0.9 dBTP while loudnorm reported
  -1.0. Measure the **delivered** file with `ebur128=peak=true` and read the
  "True peak / Peak:" line — that is YouTube's own meter. (`ebur128` prints no
  `Peak:` line at all unless `peak=true` is passed, so a missing value reads as None.)
- **A track from a stock/free library is usually mastered hot** (-7.8 LUFS / +1.0
  dBTP vs a -16 LUFS master here). Re-level any *fetched* bed with two-pass loudnorm
  to the master's level before mixing; never re-level the owner's own file.
- **`loudnorm` misses its target on high-crest input.** edge-tts is ~20 dB crest, so
  it hits the true-peak ceiling first and settles at -17.1 instead of -14. Report the
  real number; forcing it means compressing the read to death. A second compressor +
  limiter stage to squash crest is the fix when the target must be met.
- **ffmpeg rejects long `volume` expressions** (~2.5 kB of nested min/max →
  "Error when evaluating the volume expression"). Build the envelope as a numpy
  audio file and apply with `amultiply`; a file is also measurable afterwards.

## Clip-standard defects — fixed 2026-10-27 (detail in 2026-10-27.md)
Three defects shipped on every channel; all fixed. Kept short here because the
fixes are in git: (1) the channel-name badge was a red plate painted by
`compose.draw_title()` -- `build.py` now passes `""`, and note ch1's remaining
"red" pixels are *orange art*, which a generic reddish-pixel count false-flags;
(2) `mix_bed()` needed `alimiter=limit=0.7943` or the bed broke the true-peak
gate; (3) `karaoke.build_ass` ended each line 0.25 s early, a blank band at every
boundary -- now `hold = max(dur, next_start - start)`.
- **The lesson: the verifier could not see defect 3.** Sampling 21 instants missed
  a 0.25 s hole (1 of 11). `caption_gaps()` now decodes *every* frame at 270x480
  (ink is a fraction, so scale-invariant) and must skip a blank run at frame 0 and
  one ending on the last frame, or every clip fails.
- **YouTube `videos().update(part="status")` needs the whole status object.** A
  partial body returns HTTP 200 and changes nothing. Read, drop the read-only
  fields, resend.

## Daily logs
- `2026-10-30.md` — **competitor research + strategy + quality gate** (this repo,
  not yt938): the measured market per niche, the ch4-token/channel mismatch, the
  `quality_gate.py` + `measure.py` tools, and what remains (owner decision on ch4).
- `2026-10-27.md` — **the empty-pod audit above**: what was lost, the corrected
  YouTube state (ch2 12-min is public + a leftover private duplicate), the Gemini
  free-tier 429, and the push 403. Also covers the clip-standard defect fixes
  (badge, true peak, caption gaps) from the same day before the loss.
- `2026-10-26.md` — **automation system document** for ch4 + song-video
  (`docs/automation-system.md` + `docs/automation-pipeline.json`, commit 04b7906).
  Read it for the measured per-stage timings and the free-tool limits. Key find:
  edge-tts on a **cold** cache failed **7 of 8 job attempts** before completing all
  22 lines — the retry loop must be at job level, and the job is resumable because
  finished lines stay on disk. Foreground commands are capped at **1080 s**.
- `2026-10-25.md` — **three workstreams**: (a) AKATH multimodal learning in
  `aeris-drive-automation` — built the schema-driven validator + 18 fixtures +
  CI, verified against Ajv, found the push blocker; (b) ch4 — ep2 written,
  `series.py` added, then **round 7**: owner rejected on-screen characters, so
  both episodes were rebuilt as background slideshows (35 variants, 0 adjacent
  repeats) with the caption centred. Read the round-7 section for the trap list
  (`hash()` seeding, the missing `library` key, the amber-text centring artefact);
  (c) **song-video** — a short story cut to the owner's instrumental, web photos
  retouched per mood, audio preserved bit-for-bit; then **round 3** on owner
  feedback (narration clarity, picture fit, slide pacing) — read the
  "song-video round 2" section for the retrieval-measurement trick and the
  `--force` vs `--refetch` trap; then **round 4** made the music bed optional
  (Openverse fallback, fetched-bed re-levelling, attribution, `--no-music`).
- `2026-10-24.md` — Thai TTS quality lab (`tts_lab/`): 5-variant audible demo,
  text-prep recipe, number spelling, two-pass loudnorm. Note: this pod had an
  **empty** `/workspace/project` — the dharma-channel scripts were gone.
- `2026-10-20.md` — cold-start inspection, bootstrap, lunargo.net investigation,
  dharma-channel build (14 clips), GitHub/OAuth audit
- `2026-10-21.md` — YouTube OAuth solved; multi-channel refactor; genx channel
  (ปรัชญาชีวิต) content + 14 videos; first verified upload; **long-form (10-15 min)
  narration rolled out to all 28 episodes, then videos + shorts + previews rebuilt
  from it (rounds 4-6)**

## This sandbox - environment facts (verified)
- agent server: `http://localhost:60000`; auth header `X-Session-API-Key: $SESSION_API_KEY`.
- Secret store: `GET|PUT /api/settings/secrets`, `GET|DELETE /api/settings/secrets/{name}`.
  PUT body `{"name","value","description"}`. Use it to move credentials without chat.
- Preview URLs are **per-pod**: `work-1-<hash>...` -> 12000, `work-2-<hash>` ->
  12001, where `<hash>` changes on every restart. Read the current pair from the
  session's work_hosts block; never reuse a remembered one.
- No browser inside the sandbox: OAuth must use a public-callback server
  (see `dharma-channel/scripts/yt_auth.py`), never `run_local_server()`.
- `numpy` installed, used by the music synth.
- **ffmpeg is NOT preinstalled** and the sandbox is ephemeral: after a restart
  `ffmpeg`/`ffprobe` are missing. `sudo apt-get install -y ffmpeg` works
  (`openhands` is in the `sudo` group) but plain `apt-get` fails on the dpkg lock.
- **`ss`/`netstat`/`lsof` are NOT installed** — a `(ss ... || netstat ...) | grep`
  port check returns empty and looks like "port free" even when it is BUSY.
  Use a Python `socket.connect_ex` probe instead. This cost a real bug: a second
  `http.server` on 12000 failed silently and the old dharma page kept being served.
- **Nothing auto-starts in this sandbox.** PID 1 is `openhands-agent` (not init);
  `systemd` is `offline` and `cron` is NOT running, so there is no daemon to install
  that would bring a server back after a pod restart. Background processes die and
  every preview link 502s until something starts the server again. Fix that works:
  run `bash .agents/skills/ch4-video-production/scripts/ensure_review_server.sh`
  (idempotent, socket-probes the port, then verifies via real HTTP 200) as the FIRST
  action of a session. `AGENTS.md` at the repo root now says so, because an agent
  only reads a skill if it thinks to invoke it.
- Serve both channels from one port: `site/` holds symlinks `dharma -> ../output`
  and `genx -> ../output-genx`; `python3 -m http.server 12000 --directory site`.

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

## Recovering "lost" work (2026-10-27) — the sandbox is the backup
A new pod can come back empty while the work still exists: it lives in the
**previous conversation's sandbox**, which is `PAUSED`, not deleted.
- **Fastest, exact:** `POST /api/v1/sandboxes/{sandbox_id}/resume`, then poll
  `GET /api/v1/app-conversations?ids={conv_id}` until `sandbox_status: RUNNING`
  -> returns `conversation_url` + `session_api_key`. Read files with
  `GET {base}/api/file/download?path=<absolute>` (query param, not a path
  segment); `GET /api/file/archive?path=<dir>` returns a git-format patch of the
  whole tree. Works from a *different* conversation's key -- the sandbox is
  per-account. Do this FIRST, while the sandbox still exists.
- **Fallback:** `GET /api/v1/app-conversations/{id}/download` -> zip of
  `event_*.json`; replay `file_editor` ops in order, then terminal heredocs.
  Rebuilt 85 files with 0 syntax errors. Good enough to read, not authoritative.
- **The real defect: nothing was ever pushed.** `git remote -v` is empty; 50
  local commits. `permissions.push: true` from the API is **not** evidence of
  push ability -- only the push is (it was 403). Push somewhere real.

## Index-keyed caches: the bug that hides behind every gate (2026-10-28)
Every cache in yt938 keyed on the line/shot index, so editing content left the old
media in place. The clip is then a mix of two drafts and **nothing inside it
reveals that** -- all gates passed while ch1's captions said text the voice never
spoke. Fixed in four places: voice mp3 (sidecar `sha256(prep_text(line))`),
`.seg.wav` (stamped size:mtime of the mp3), `frame_*.jpg` (hash of source image +
caption + title), `_chunk_*.mp4` (hash of frames + ASS + audio). Legacy files are
adopted only when `len(text)/dur` is 7-15.5 chars/s, so the first run repairs the
corruption instead of blessing it. Gate: `verify_clip.py --voice-dir`. Tests:
`ops/test_voice_cache.py`. Whisper similarity went 0.21 -> 0.93.
- **`\k` spans to the NEXT word's start, not `end-start`.** A \k is how long the
  highlight stays, so the word's own length drops every pause and the sweep runs
  ahead of the voice (2.49 s on ch1 line 0). Fixed in `karaoke.line_event`.
- **A gate that can never pass reads as a gate that always passes.**
  `POSTER_SHARP_MIN` was 15.0; the sharpest poster in the tree is 10.1, so it
  failed on every clip -- and the "sample passed all gates" claim was made without
  ever passing `--poster`. Now 3.0, calibrated (gaussian r=3 = 2.5, r=2 = 3.45).
  Always ask what the *worst* real artifact scores before trusting a threshold.
- **Pollinations ignores `model=`** and caps size at 576x1024 for any request
  (sana/flux/turbo are byte-identical). So "low-res + sharp" is forced, and drawn
  line-art styles are what survive the 1.9x upscale -- which is what the owner
  asked for anyway. Rate limit 1 image / ~45 s / IP.
- **FLUX ZeroGPU quota is out for long stretches**; `anime.generate` retries four
  spaces so a dead FLUX costs minutes *per image*. `yt938/imgutil.py` probes once
  per process and falls back to Pollinations (`YT938_IMG_BACKEND` forces a choice).

## The owner's review page + the skipped gate (2026-10-28)
- **The review page was 100% dead links.** `make_index.py` writes the page to
  `output/review/index.html` but the episodes live in `output/<ep>/`, so every
  link needs `../`. It returned **200 and looked perfect** while the clip, all
  stills, `build.log` and `meta.json` 404'd; only the demo video was right, which
  is why it survived. The three decision pages (`channel-styles`, `voices`,
  `style`) were also **orphaned** -- same dir, nothing linked to them, so K could
  not reach the things he was asked to judge. Test: `ops/test_review_links.py`
  (48 links, 0 broken over HTTP). **A page that renders is not a page that works.**
- **The narration gate could be skipped and still print "STANDARD MET".**
  `verify_clip.py` only tests speech vs the stem when `--narration` is passed;
  without it the energy fallback ran, which cannot tell narration from a music bed
  (a music-only clip passed it). It now finds `narration.wav`/`script.txt` beside
  the clip automatically, and prints **INCOMPLETE / exit 3** when it cannot check.
  Test: `ops/test_verify_clip.py`.
- **Do not trust a narration stem whose length does not match the clip.** The ch1
  tree held a **110 s smoke-test `narration.wav` next to an 896 s clip**, and
  measuring against it gave "23% narration coverage" -- a number that looked like a
  real defect and was pure artifact: the stems share no timeline, so every second
  the stem calls silent is speech in the clip. The verifier now rejects a stem more
  than 10% off the clip's length and says so. Before blaming the clip for an audio
  gate, check the stem is the one the clip was built from (compare `ffprobe`
  durations).
- **One hung image killed an hour-long build** (734 s, then abort). Pollinations
  timeout 180 s x 5 attempts = ~15 min worst case per image; now 90 s x 3 (~5 min).
  build.py still **aborts rather than skipping** a frame: images and timeline are
  zipped, so a dropped still shifts every later caption onto the wrong picture --
  the narration-mismatch defect. Stills are cached, so a rerun resumes at the frame
  that failed. `/tmp/build_loop.sh` auto-resumes until the mp4 exists.
- **A gate threshold in absolute dBFS does not transfer across masters.** The music-bed
  gate demanded the bed be >= -25 dBFS in the narration gaps. The reference clip's bed
  sits ~13 dB under the voice, which on a -14 LUFS master is about -27 dBFS -- so a
  correctly mixed clip FAILS and a loud master passes a too-loud bed. The owner's real
  complaint ("no music") is a *ratio*, so the gate now tests headroom (6-20 dB under the
  voice). Two measurement bugs rode along: the bed in a gap was averaged over the whole
  second (the fade in/out drags it ~2 dB low -- use the loudest 0.25 s window), and
  "silence" was stem rms < 1 LSB (use < -60 dBFS).
- **A fixture that points at a deleted file makes the test silently smaller.** Three of
  five cases in `ops/test_verify_clip.py` referenced `ch2_dhamma_*` paths that were gone,
  so they stopped running while the test still printed success. Point fixtures at assets
  that exist (`ch2_ep01`), and make each case assert the gate it targets actually fired.
- **`ops/verify_clip.py` writes `verify.json` beside the clip** and `yt938/make_index.py`
  shows it as a verdict tag, so K can tell a current build from a stale one. The first
  write died mid-file: gate results are numpy bools, and `json.dump` cannot serialize
  them -- coerce to `bool` and write `.part` + `os.replace`.

## User preferences
- User is on **Windows (PowerShell)**, not Linux. Do NOT hand them `mkdir -p`,
  `chmod`, or `&&` one-liners -- PowerShell 5 rejects `&&` and has no `chmod`.
  Prefer UI steps, or give native PowerShell (New-Item / Move-Item / `;`).
- Communicates in Thai; wants concise Thai answers.
- Wants evidence and verified results, not claims.

## Free slide effects (2026-10-27)
Owner asked for free effects so slides look more interesting. Answer is
**`yt938/effects.py`** -- no download, no key, no quota: ffmpeg already ships
everything.
- **Ken Burns** via `zoompan`. Use **`d=1`** and an explicit **`fps=30` filter
  before zoompan**, or the clip is the wrong length (a larger `d` multiplies
  frames because the input is `-loop 1`; without the fps filter it came out
  2.93 s instead of 3.5 s) and the burned captions drift off the narration.
  Normalise the move by the shot's own frame count so it ends where it should.
- **Cut variety**: `xfade` has **58 transitions**; using `fade` on every cut
  reads as static. Draw one from the shot index so neighbours differ and the
  build stays reproducible.
- 6 moves / 18 transitions chosen to look like editing (fades, dissolves,
  zooms, light blooms), not like a template (wipes, slices).
- Output files roughly double in size (motion adds bits).

## Caption-ink floor was too low (2026-10-27)
`CAPTION_MIN` in `ops/verify_clip.py` was **0.0006**, but lead-in frames (with a
vignette grade) measure up to **0.0014** and real captions start at **0.0088**.
The floor sat *inside the noise*, so the deliberate lead-in split into a short
run that no longer started at frame 0 and the gate reported a false
mid-narration gap. **Raised to 0.004.** Always re-run
`ops/test_verify_clip.py` after touching the verifier -- it still rejects a real
caption gap at the new threshold.

## Signed-in Google session (2026-10-28) — skill: google-session-browser
Gemini/Flow **API key is quota-dead** (429 everywhere). Use the
**`.agents/skills/google-session-browser`** skill: `bash .agents/skills/
google-session-browser/scripts/session.sh start` (reinstalls display stack +
playwright after a restart; reuses the persisted signed-in profile). Owner:
kongkeat.938@gmail.com — NEVER type their password; they sign in via the noVNC
link. Detail in `2026-10-28.md`.

## Two modules named `imgutil` — the art was never FLUX (2026-10-28)
`build.py` did `import imgutil`, but **`compose.py` inserts its own directory at
the front of `sys.path`**, so the name resolved to `ch4-anime/scripts/imgutil.py`
(the **Pollinations `sana` client, ~0.59 MP, upscaled**) instead of
`yt938/imgutil.py` (FLUX.1-merged). Silent -- no error, no log. Every still in
ch1/ch2/ch4 was 578x1020 or 627x940; **no 1088x1920 file existed**. Fixed by
loading the client by path (commit **24e7166**); guarded by
`ops/test_img_backend.py`, which reproduces the trap and asserts the FLUX client
loads. General rule: **never rely on `import <name>` when two dirs on sys.path
ship that basename -- load by path.**
Blockers for the rebuild (free tools only): **ZeroGPU quota is per-IP and shared**
-- all 4 FLUX spaces say "Try again in 20:xx:xx" (~20 h), and an `HF_TOKEN` is
what would raise it (none is set); **`GEMINI_API_KEY` is free-tier, 429 on
input tokens per minute**, and its images are the same 572x1024 = 0.59 MP the
owner rejected. The signed-in Gemini web UI is stuck on Flash-Lite (text-only);
the other models are `aria-disabled`. Detail in `2026-10-28.md`.

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
