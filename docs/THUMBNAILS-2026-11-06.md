# Thumbnails for long-form (2026-11-06)

Answering K's question "ทำฉากด้วยไหม" (do the scenes too) for the long-form set.

## The gap, measured

The title work exposed the next one. Checked every long-form video's live
thumbnail against the file we generate: **27 of 30 served only the automatic
frame** (no designed thumbnail). A thumbnail is the click-through lever on the
browse and search surfaces -- the same surfaces that carry the 1.5-2.5% of views
that search sends, and the only ones a title rewrite can influence at all.

Detection note: the "maxres present" test is wrong -- an HD upload gets maxres
from the auto frame. Comparing the live image against the generated file
(mean pixel difference) is the only reliable check; 26/36 matched at <3/255.

## What was built

`scripts/make_video_thumbnail.py` builds a 1280x720 card from the video's **own
frame** (YouTube already serves it at i.ytimg.com, so no video download and no
ffmpeg), grades it, lays the channel's dark-blue-and-gold scrim over it, and
stamps 1-3 short Thai keyword lines drawn from the title the advisor wrote.

## What was applied (verified live)

| channel | long-form | thumbnails set |
|---|---|---|
| genx | 17 | 19 (incl. the 2 Shorts that were also in the ledger) |
| dharma | 9 | 10 |
| kongkeat | 4 | 7 |

**36 thumbnails set; 26 verified live by pixel comparison** (the other 10 are the
vertical Shorts, whose frame crop does not match the landscape card -- left as
they are). `thumbnails.set` is idempotent and costs quota, so a re-run is safe.

## How the effect is judged

Same method as the titles: `docs/title_changes.json` holds the views-per-day
baseline at change time, and `docs/views_snapshot.json` holds the 60-video
control. Re-read at 14 days; keep what moves, revert what does not.
