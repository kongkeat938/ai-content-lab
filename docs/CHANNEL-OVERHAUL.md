# Channel overhaul — what the numbers say and what we will do

Measured 2026-11-03 with the YouTube Data API. Two consultants (Gemini
`gemini-3.5-flash-lite` and ChatGPT, both driven with the real numbers attached)
were asked the same question, and the structural fixes they agreed on were then
applied with `scripts/channel_overhaul.py`.

## The measurement

| ch | subs | vids | Shorts views | Shorts like-rate | long views | long like-rate |
|---|---|---|---|---|---|---|
| ch1 ตาต้า GenX | 12 | 38 | 5,383 | 0.93% | 1,009 | 0.59% |
| ch2 Farmmer | 14 | 24 | 4,904 | 1.04% | **72** | — |
| ch4 เรื่องเล่าการ์ตูน | 8 | 17 | 3,215 | **1.99%** | **15** | 0% |

What the numbers actually mean, in plain terms:

- A Short is **shown** to a scrolling viewer; a long video has to **win a click**.
  So Short views are not evidence of interest, and long views of ~0 are not
  evidence that long content is unwanted — they are evidence that nothing on the
  channel asks for the click.
- **Likes are the only voluntary signal.** A viewer who was pushed a Short can
  still choose to like it, so like-rate is the honest quality number. ch4's 1.99%
  (best clip 3.27%) says family stories are the strongest content of the three.
- **Traffic is not moving inside the channel.** ch2 sent 9/14 Shorts to another
  video; ch1 only 2/16 and ch4 only 3/11 — so the best-liked clips had no door
  out. This is the real leak, and it is cheaper to fix than to make more clips.

## What was changed today

`scripts/channel_overhaul.py` (idempotent, `--dry-run` first) set, on all three
channels:

- **a trailer** — the clip a non-subscriber sees first: ch1 `07zfyXOmvZw` (1,405
  views), ch2 `oIsloIKa0J4` (1,290), ch4 `udi7bekVJiA` (1,079).
- **playlists** so "search the channel" is a shelf, not a wall:
  ch1 → ปรัชญาชีวิต 13 / 1 นาทีภาษาอังกฤษ 4 / เรื่องสั้น 5;
  ch2 → Shorts 16 / หลับลึกทั้งคืน 10 / ตอน 10;
  ch4 → Shorts 14 / ตอน 6.

All of it is reversible from the same script.

## The plan (ordered by impact)

1. **Fix the doors before making more clips.** Every Short gets a related video
   and a pinned comment pointing to the next clip. The pipeline already has
   `promote_channels.py` / `publish_shorts.py`; they are not being called for
   every Short — that is the bug behind 2/16 and 3/11.
2. **Test hooks, do not scale output.** Publish 1 Short/channel/day with a
   deliberate hook; change one variable at a time.
3. **Build series, not clips.** ch2 "ธรรมะ 1 นาทีก่อนหลับ", ch1 "ความจริงที่ไม่มี
   ใครบอก", ch4 "เรื่องเล่าที่ทำให้คิดถึงบ้าน" — three linked clips each.
4. **Only then long-form**, 4–7 min, on a topic a Short has already proven, with
   the Short's viewers as the entry point.
5. **Positioning:** ch1 stops mixing random English lessons and unthemed short
   films — philosophy with English as a component, not English as a subject.
   ch2 = sleep/dharma only. ch4 = family stories only.

## The one metric

**Viewed vs Swiped Away** on Shorts (target ≥60% ch1, ≥65% ch2, ≥70% ch4), read
alongside 3-second retention, average percentage viewed and related-video clicks.
Views and subscribers are outputs, not the target.

## Do not

- Do not mass-produce with the same hook — 100 clips with a losing hook fix nothing.
- Do not make quote-only Shorts; a quote earns a view but no reason to return.
- Do not open a loop the clip never pays off.
- Do not build long videos for watch time; a 20-minute clip abandoned at 20
  seconds loses to a 5-minute clip watched to the end.
- Do not delete the old clips — the 1,079-view / 2.32% clip is the evidence to
  build on.
- Do not expect a hashtag to be a strategy: ch2 tags #Shorts on 14/14 and its
  long-form still earned 72 views.
