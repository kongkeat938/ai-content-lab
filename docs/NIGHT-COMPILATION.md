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
# 1. build the audio, repeating the pieces until it reaches 90 minutes
python3 scripts/make_compilation.py \
    --out work/night_01/compilation.mp3 \
    --part content/night_01/0*.txt \
    --work work/night_01 --minutes 90

# 2. cover + video (one graded card, a 24 s drift looped under the track)
python3 scripts/make_night_video.py \
    --audio work/night_01/compilation.mp3 \
    --image assets/images/ep02/img00_00.jpg \
    --out work/night_01/video.mp4 --loop-seconds 24

# 3. measure before claiming it is done
python3 scripts/verify_night.py work/night_01/video.mp4
python3 scripts/test_night.py          # guards the gates themselves
```

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

## What is not here yet

* **A real 90-minute script.** The rail is proven, but the pieces in
  `content/night_01/` are six short breathing/relaxation scripts written as a
  test set, not the dharma talk the channel needs. The cost of the format is the
  script, not the render: 94 min of audio is ~12 minutes of synthesis.
* **Music.** The bed is synthesised, deliberately — every free music source is
  rate-limited or blocked by the sandbox proxy. A real bed would need an
  Openverse fetch on a machine that can reach it.
