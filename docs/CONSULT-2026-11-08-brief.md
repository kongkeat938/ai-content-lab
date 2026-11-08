# Brief: the first two minutes are the whole game — what do we change?

You are advising a small Thai YouTube operation. Answer in Thai. Be concrete and
rank your advice by expected effect. Do not repeat our numbers back; use them.

## Measured facts (YouTube Analytics API, 2026-11-08)

Three channels, Thai long-form + Shorts. Long-form only counts toward the
1,000-sub / 4,000-hour monetization threshold; Shorts views do not.

| channel | subs | videos | views/28d | watch-h/28d |
|---|---|---|---|---|
| genx (ปรัชญาชีวิต) | 174 | 115 | 19,760 | 86.5 |
| dharma (ธรรมะก่อนนอน) | 83 | 131 | 10,861 | 56.5 |
| kongkeat (เรื่องเล่า) | 10 | 78 | 5,645 | 19.3 |

Our best long-form: `F4qFHoVpEyI`, 120 min, 337 views, **13.3 watch-hours**,
average view duration 379 s = **5.2%**. Per view that is 0.037 watch-hours —
**about 25x more watch-time per view than a Short** (Short ≈ 0.0015 h/view).

### Audience-retention curve of that video (elapsedVideoTimeRatio → % still watching)

| time | still watching |
|---|---|
| 1 min | 101.6% |
| 2 min | 29.3% |
| 4 min | 23.6% |
| 5 min | 19.5% |
| 8 min | 14.6% |
| 10 min | 11.4% |
| 20 min | 6.5% |
| 30 min | 4.9% |
| 60 min | 4.1% |
| 120 min | 1.6% |

**71% of everyone who starts leaves within the first two minutes.** After that
the curve is almost flat.

## What the video is (so you can judge the fix)

- Audio: one calm Thai male voice (th-TH-NiwatNeural), slow, line-per-line
  narration over a soft bed at -30 LUFS. Chapter per theme.
- Video: a Ken-Burns still image per chapter, crossfaded, no motion graphics,
  no presenter, no captions burned in.
- It opens with an ~11-second spoken "hook" sentence, then the first chapter.
- Title: "ปรัชญาชีวิต — วางความโกรธที่เก็บไว้นาน รวมข้อคิดให้ใจเบาลง ฟังเพลิน ๆ"
- Description opens with "รวมข้อคิดและปรัชญาชีวิตสำหรับคนวัยทำงาน 25 นาที ..."
- Thumbnail: a custom calm-philosophy card.
- Traffic: almost entirely the YouTube feed (no external).

## The question

1. With a **two-minute cliff**, is the realistic fix the **content/audio** (what
   is said and how), the **first-frame/visual**, or the **packaging** (title,
   thumbnail, first line of description)? Rank by expected lift, and say what
   evidence you would expect to see if your pick is right.
2. Give a **specific first-60-seconds script** (in Thai) for a 25-30 minute calm
   philosophy long-form that you believe beats 29% at the 2-minute mark. Name the
   single most important thing that script does differently from a video that
   simply starts reading the first chapter.
3. Should we **cut the length to ~10-12 minutes** while the curve is this steep,
   or keep 25-30? Give the arithmetic for watch-hours per upload under each.
4. Name the **one measurement** we should watch for the next 7 days to know if
   we are winning, and the number that means "stop".
