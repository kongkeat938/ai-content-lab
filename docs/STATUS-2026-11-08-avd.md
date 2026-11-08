# STATUS 2026-11-08 — the low-AVD fix, shipped and live

Task **yt938-2**. Round 3: act on the advisor panel's verdict for the long-form
rail's very low average view duration, and prove it on a real upload.

## The problem, measured

The channel's best long-form (a 120-minute dharma file) held an
`averageViewDuration` of **379 s = 5.2%** of its length. The cause was the format:
the whole file was **one static card** (`make_night_video.py`) drifting under the
narration for two hours, so the screen never changed. YouTube reads that as
low-effort, reused content.

## The panel (four camps, 2026-11-07)

`docs/PANEL-2026-11-07c.md`. gemini-3.5-flash-lite, gemini-3.6-flash,
gemma-4-31b-it and gpt-oss-20b all answered (DeepSeek and Zhipu were unavailable).
Their ordered fix:

1. a spoken **hook** in the first ~20 s (the promise that earns the next minute),
2. cut the file to **20–30 min** (5.2% of 25 min is a far easier number to push),
3. **change the picture per chapter** — not one card looping for hours,
4. do **not** pump 8–10-hour loops: that is the "reused content" trap at YPP review.

## What shipped

- **`scripts/make_chapter_video.py`** (new) — renders **one card per piece** from
  the per-piece durations `make_compilation.py` already records, each with its own
  Ken Burns drift and chapter label, crossfaded so the screen changes every few
  minutes while the audio never stops. True-peak guarded like the old rail.
- **`scripts/make_compilation.py`** — new `--hook`: a one-line promise spoken once
  before the looped body; the body is shortened by the hook's own length so the
  file still hits its target.
- **`scripts/build_night.py`** — new `--chapters` and `--hook`; generates one
  image per piece. dharma/ch4 keep the single-card sleep format (correct for a
  leave-it-playing file).
- **`scripts/test_chapter_video.py`** (new) — locks one-card-per-piece, "consecutive
  chapters must differ in luma", `tv` colour range, true peak ≤ -2.9 dBFS.
- **`.github/workflows/genx-longform.yml`** — `--chapters` + a real hook sentence.

## Proof on CI (run 42431978059, SUCCESS)

```
hook: 11s
repeating the 8 pieces x2 to reach 25 min
voice track: 26.3 min
{"minutes": 26.3, "lufs": "-14.4", "true_peak_dbfs": "-3.1", ...}
{"duration_sec": 1580.71, "video": "1920x1080", "chapters": 17,
 "chapter_seconds": [10.67, 88.58, 105.47, ...],
 "true_peak_dbfs": -3.2, "audio_gain_db": 0.0}
loudness      -14.4 LUFS   true peak -3.2 dBFS
{"verdict": "pass", "failures": []}
```

17 cards (1 hook + 8 pieces × 2 cycles), 26.3 min, -14.4 LUFS, true peak -3.2 dBFS.

## Live

`ch1_auto_202645` → **https://youtu.be/3HCOe1jZj2c** — ตาต้า GenX, **public**,
26:21, HD processed (maxres thumbnail 200). Uploaded by `publish-ch1` with no
browser and no human; the manifest recorded the id, so a re-run cannot double-post.

## What is not yet measured

Whether the change lifts AVD. The old baseline was 5.2% on a 120-minute file; the
next honest number is this 26-minute file's AVD once Analytics has a week of data.
Do not claim a win before that number exists.
