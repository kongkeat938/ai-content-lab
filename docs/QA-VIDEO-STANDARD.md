# Q/A long-form video standard (reference look)

The owner's target (2026-11-17) is a Google **Veo** clip: a realistic picture, a big
Thai question, a Thai answer caption at the bottom, a warm voice. This page records
what that clip is, what we can reproduce for free, and how to build it.

## What the reference is

- File `เกร็ดความรู้รอบตัวและวิทยาศาสตร์…_7412fc21.mp4`: 4.03 s, 1280x720, 24 fps, aac.
- Its metadata carries **C2PA**: `Created by Google Generative AI`,
  `trainedAlgorithmicMedia`, `Added imperceptible SynthID watermark` — i.e. **Veo**.
- Frame: a real-looking Thai woman presenter, big Thai question "ทำไมท้องฟ้า ถึงเป็นสีฟ้า?"
  on the left, answer "เพราะแสงแดดกระเจิงกับอากาศ" bottom-centre.

## What we can do, measured (2026-11-17)

| Piece | Free path (this repo) | Result |
|---|---|---|
| Realistic still | `gen_cover_image.py --style photoreal` (pollinations, no key) | vision-graded **8/10** on object/nature, 6/10 on a face |
| Motion | Ken Burns push + a new still every beat | no static card |
| Thai question + caption | PIL text card (Kanit / Prompt fonts) | correct Thai, top-left + bottom-centre |
| Voice | edge-tts `th-TH-PremwadeeNeural` (fallback `NiwatNeural`) | free, ~9 chars/s |
| Moving presenter | **not free** — Veo is 404 on our key; every matching API is paid | gap |

Paid options for the presenter look (Krea API, price list 2026-11-17):
Wan 3.0 from **$0.075/s**, Kling 3.0 from **$0.084/s**, Kling 4.0 from **$0.157/s**,
Veo 3.1 **$0.80/s**. A 30-minute video at Wan prices is roughly **$135** per video —
so the free format is the standard, and a hero clip is an optional paid accent.

## The standard that shipped: real b-roll + a designed card (2026-11-17)

The reference's essence is **a real photograph of a person**, not a photoreal still,
and a free model cannot make a believable human. So the standard uses **REAL
licence-clean stock video** as the base and lets the *design* carry it:

- base = one real 1080p clip per beat, from **Coverr** via `scripts/fetch_broll.py`
  (keyless, free for commercial use, no attribution required);
- **one warm grade** over every clip (`BROLL_GRADE`: warm highlights, cool shadows,
  contrast, vignette, fine grain) so the footage reads as one story;
- a **frosted-glass card** (`text_card`): an amber question chip top-left, an answer
  card bottom-centre, a channel tag top-right — the "signature UI" a vision grader
  asked for, not a plain black box;
- Thai voice (edge-tts) and captions synced to the narration.

Measured with a vision grader (`gemini-3.5-flash-lite`), same 3-beat clip, iterating:

| Cut | Production | Thai acceptance | Appeal | Verdict |
|---|---|---|---|---|
| cold AI landscape still | 3 | — | — | "cannot pass" |
| raw stock + floating text | 4–5 | 4 | 4 | "generic stock slop" |
| + warm grade + frosted card | **7** | **8** | 6.5 | **"escapes stock slop; looks intentional"** |

This is wired into the ch4 knowledge rail: `build_night.py --engine kinetic --broll`
fetches one clip per beat and burns the captions over the graded base.

### Defect fixed while building this (measured)

The card is a single still fed to a `fade` filter; without looping it, the fade
blanks the card after ~0.5 s so **beats 2..N rendered textless** (only beat 1 kept
its card). The card input is now looped. `scripts/test_qa_video.py` locks it: it
samples a *late* frame and requires the text is still there.

## Build a clip

```
python3 scripts/make_qa_video.py \
    --script work/<job>/qa.json \
    --out    work/<job>/video.mp4 \
    --style  photoreal
```

Script shape (`qa.json`):

```json
{"title": "เกร็ดความรู้รอบตัว",
 "beats": [
   {"question": "ทำไมท้องฟ้า ถึงเป็นสีฟ้า?",
    "answer": "เพราะแสงแดดกระเจิงกับอากาศ",
    "image": "sunbeams scattering through blue sky over a calm horizon"}
 ]}
```

`image` is an **English** prompt for the still (the free generator is English-first);
`question` / `answer` are the Thai text that is both spoken and drawn.

Pass `--broll` to use real stock footage per beat instead of the still — the shipped
standard:

```
python3 scripts/make_qa_video.py \
    --script work/<job>/qa.json \
    --out    work/<job>/video.mp4 \
    --broll  --brand "PCSEV"
```

Each beat then fetches a clip with its `broll` query (short English queries work
best) and writes `attribution.json` beside the work dir.

For the long-form (30-min) knowledge rail, the same method is the kinetic engine's
`--broll` mode, driven by `build_night.py`:

```
python3 scripts/build_night.py --content content/<set> --work work/ch4_know_01 \
    --engine kinetic --broll --minutes 30 --voice th-TH-NiwatNeural \
    --brand "PCSEV" --hook-file content/hooks/knowledge.md
```

`build_night.py` writes `broll.json` (one real clip per beat) and passes it to
`make_kinetic_video.py --broll`; a beat that cannot be sourced **fails the build**
rather than shipping a still into a live-action set.

## The hero-clip slot (drop-in for a paid presenter)

A paid model's output drops straight in without touching the rest of the pipeline:
put clips named `01.mp4`, `02.mp4`, … in a directory and pass `--hero-dir`. Beat `NN`
then uses its clip as the base instead of the still. The Thai question, answer
caption and voice are unchanged.

## Quality gate (must pass before upload)

`scripts/make_qa_video.py` verifies its own output, and `scripts/test_qa_video.py`
locks the format. A clip is uploadable only when:

- resolution **1280x720**, pixel format yuv420p;
- **colour range `tv`** (full/`pc` fails `verify_night.py`);
- an audio stream present;
- the question is drawn top and the answer caption bottom (a beat with no answer
  draws no caption band).

`python3 scripts/test_qa_video.py` — exit 0 means the standard holds. It is
mutation-checked: blanking the overlay, forcing `pc` range, or moving the caption
to the top each make it FAIL.

## Minimum standard — ALL channels, long-form AND Shorts (2026-11-17)

K made the approved look the **minimum bar for every upload**, and a **Short must also meet an
aspect-ratio + thumbnail standard** — "if it does not meet the standard, do not upload it,
including the old backlog." Two things enforce it, and a doc is only the *weakest* evidence:

- **Long-form:** every rail runs `scripts/verify_night.py`, which now **hard-fails** a file that
  is not 1920x1080, not `yuv420p`, or not `color_range=tv` (on top of the loudness/peak/headroom
  checks). Guard: `scripts/test_verify_night.py`.
- **Shorts:** `scripts/short_standard.py` is the single pass/fail. `publish_shorts.py` builds the
  thumbnail, checks the standard **before** `videos().insert`, and **holds** anything that fails.
  Guard: `scripts/test_short_standard.py`.

| Surface | Standard | Measured how |
|---|---|---|
| Picture | 1920x1080 (long-form) / 1080x1920 9:16 (Short) | `ffprobe` width/height |
| Colour | `yuv420p`, `range=tv`, `bt709` | `ffprobe` pix_fmt/color_range/color_space |
| Audio | −14 LUFS ±1.5, true peak ≤ −3 dBFS | `ffmpeg ebur128=peak=true` |
| Short length | ≤ 60 s | `ffprobe` duration |
| Short thumbnail | 9:16, height ≥ 640, JPG/PNG, < 2 MB | `PIL` size/format + `os.path.getsize` |

The Shorts thumbnail rule is **YouTube's own** (support.google.com/youtube/answer/72431, read
2026-11-17): 9:16 aspect, 2160x3840 recommended, minimum height 640, JPG/PNG, under the MB limit.
It is PORTRAIT — a 1280x720 thumbnail is a long-form shape, not a Shorts one.

### One grade source (do not copy the chain)
`scripts/video_grade.py` holds the single b-roll grade chain (zoom 1.06, `lanczos`, `unsharp` +
`cas=0.6`, per-clip brightness ~150). Both `make_qa_video.py` and `make_kinetic_video.py` import
it. Measured 2026-11-17: the rail's engine had drifted to **LapVar 15.4** on a clip the approved
chain scored **46.6** on (~3x softer) because it kept a private copy. `scripts/test_video_grade.py`
fails if the two ever diverge again.
