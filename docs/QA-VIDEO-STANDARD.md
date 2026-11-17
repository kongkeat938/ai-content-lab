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
