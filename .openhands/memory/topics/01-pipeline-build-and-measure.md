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
