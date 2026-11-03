# NIGHT COMPILATION — the long-form rail

The channels ship 10–12 minute episodes. The dharma-before-sleep niche does not
reward that: the videos that win it are **82–240 minutes** and people leave them
playing all night (measured, see `ax-workspace/docs/MARKETING-STRATEGY.md` §1).
This rail produces that format.

Free tools only: `edge-tts` for the voice, the synthesiser in `scripts/make_bed.py`
for the bed, `ffmpeg` for everything else.

## Pipeline

```
content/<set>/NN_*.txt ──> make_compilation.py ──> compilation.mp3
                                │  (edge-tts + loudnorm2)
                                ▼
                       make_night_video.py ──> video.mp4
                                │  (poster cover + a slow drift, looped)
                                ▼
                          verify_night.py        (exit 0 = pass)
```

```bash
# one command: build -> verify, and the verifier's verdict is the exit code
python3 scripts/build_night.py \
    --content content/night_dharma_01 \
    --work work/night --minutes 120

# or step by step
python3 scripts/make_compilation.py \
    --out work/night/compilation.mp3 \
    --part 'content/night_dharma_01/[0-9]*.txt' \
    --work work/night --minutes 120
python3 scripts/make_night_video.py \
    --audio work/night/compilation.mp3 \
    --image assets/images/img00_00.jpg \
    --out work/night/video.mp4 --loop-seconds 24
python3 scripts/verify_night.py work/night/video.mp4
python3 scripts/test_night.py          # guards the gates themselves
```

`build_night.py` exists because chaining the three by hand means the last
command's exit code decides whether CI is green — a build whose true peak is
over the gate still "passes" if nobody reads the log. It makes the verifier's
verdict the process verdict and writes `receipt.json` with the measured numbers.

## It runs unattended

`.github/workflows/night-compilation.yml` builds the compilation on a GitHub
runner — weekly and on demand — then verifies it, attaches the media to a
Release, and opens one review issue with the numbers. It needs **no secret to
build** (edge-tts, ffmpeg and the bed synthesiser are all free). It does **not**
upload to YouTube: ak does not upload, K reviews the first work of each channel.
A fingerprint of the content + rail is the release tag, so a weekly run on an
unchanged set skips instead of re-rendering 40 minutes of CI for nothing.

Proven end to end on 2026-11-03 (dispatch → build → verify → release → issue,
all green): release `night-857bc8fdda62`, issue #3.

## Measured result (2026-11-02, this pod)

| | |
|---|---|
| length | **94.1 min** (6 pieces × 22 cycles) |
| loudness | **-14.5 LUFS** |
| true peak | **-3.1 dBFS** |
| picture | 1920x1080, `color_range=tv`, 25 fps |
| bed | **20.5 dB under the voice** |
| audio | 90 MB mp3 · video | 427 MB mp4 |

## The three things that are easy to get wrong

1. **`-stream_loop -1` + `-shortest` does not stop the video.** The endless input
   never ends, so the output ran 322 s against a 257 s track and every gate still
   passed. An explicit `-t <audio duration>` is what bounds it. The verifier now
   compares the two stream durations, and `test_night.py` reproduces the defect.
2. **The bed level is a ratio, not a number.** Free tracks differ by ~9 dB, so a
   fixed multiplier lands the bed on top of the voice on one build and inaudible
   on the next. `mix()` measures the real level of the voice and the bed with the
   verifier's own `ebur128` and re-levels to `BED_UNDER_VOICE_DB` (16 dB).
3. **A loop must be whole-cycle.** Every LFO in `make_bed.py` runs an integer
   number of cycles across the clip, so sample 0 meets sample N and the seam is
   smaller than the waveform's own step-to-step change (measured 0.00219 vs
   0.00246). `ffmpeg`'s `tremolo` cannot do this — its rate floors at 0.1 Hz.
4. **The mp3's true peak is not the video's.** The track is mastered to
   `TP<=-3.0`, but the AAC pass the video needs overshoots it (measured -2.9,
   verified -3.2 in the shipped file). `make_night_video.build()` now measures
   the finished mp4 and re-encodes the audio lower until the gate holds, and
   records `true_peak_dbfs` in the `.info.json`. A rail that measures the
   intermediate and not the artifact ships a file that fails its own gate.

## First real build (night_dharma_01)

* Script: `content/night_dharma_01/` — 28 dharma-before-sleep pieces, 16 457
  characters, **30.2 min** of speech (measured: sum of the 28 part durations);
  `make_compilation` cycles it to length (4 cycles for 120 min).
* Out (120 min target, measured by `verify_night.py` on the mp4): 120.8 min ·
  **-14.5 LUFS** · true peak **-3.1 dBFS** · 1920x1080 `tv` · bed 20.6 dB under
  the voice · `moov` first (seekable) · mp4 717 MB.
* Verified by `verify_night.py`: **pass**.

## What is not here yet

* **A script long enough to avoid heavy repetition.** 30 min of speech is still
  cycled 4x to reach 120 min; a full 90-minute episode wants ~90 min of distinct
  speech. The cost of the format is the script, not the render: 120 min of audio
  is ~16 minutes of synthesis. Each cycle is now **rotated** (piece order shifts)
  so a listener who leaves the file playing does not hear the identical sequence
  back to back, but the pieces themselves still repeat.
* **Music.** The bed is synthesised, deliberately — every free music source is
  rate-limited or blocked by the sandbox proxy. A real bed would need an
  Openverse fetch on a machine that can reach it.
* **The upload step.** The rail builds and verifies; it does not publish. That is
  deliberate (ak does not upload), and it is the one line to add once K approves
  the first file: point `publish_youtube.py` at the Release asset with the ch2
  token.
