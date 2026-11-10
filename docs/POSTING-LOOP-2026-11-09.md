# The posting loop — one clip, wait, read, repeat (2026-11-09)

K's rule: **post one clip, wait 2-3 hours, look at how it did, then post the
next.** Good reception → keep the shape. Bad reception → change it. Loop across
all three channels until a shape works. Never post several at once, never repeat
a losing shape, and keep the cadence human — a person does not dump five clips in
a minute.

The rail already had a *cap* (a daily ceiling) and a *gap* (`MIN_GAP_HOURS`). What
it did **not** have was the middle of the loop: nothing read the last post's
result, so nothing connected "that clip flopped" to "the next clip should be
different". This is that missing link.

## What was wrong (measured, not assumed)

- **Bursts.** `foreman.py` dispatched `publish-shorts` with `per_run: 2`, so one
  dispatch posted two clips. K's rule is one at a time. Fixed to `per_run: 1`.
- **No reception check.** The rail spaced posts by time only; it never asked how
  the previous one did. Fixed: `scripts/pace.py` grades the last post.
- **Static shape choice.** `winning_first()` always put the *historically* best
  hook shape first, from a 2026-11-03 measurement. It never adapted. Fixed:
  `pace.order()` keeps the winning shape after a good post and switches after a bad
  one.

## The loop (`scripts/pace.py`)

`gate(channel)` decides whether the next Short is due and grades the last one:

1. **Gap.** Refuse until `MIN_GAP_HOURS` (2.0 h) since the last post. The foreman's
   30-minute heartbeat supplies the jitter above the floor, so real gaps land in
   the 2-3 h window rather than exactly on 2.0.
2. **Reception.** Compare the last post's views-per-hour with the channel's own
   **top-quarter** rate (clips ≥ 12 h old). Above → `good`; below → `bad`; too few
   clips to be sure → `unknown`.

`order(todo, verdict, last_shape)` then sets the queue: `good`/`unknown` keep the
measured winning shape first; `bad` moves the *other* shape to the front, so the
next clip is a change.

### Why the top quarter, not the median

Half of dharma's Shorts sit at zero views (the zero-view cluster this whole effort
is about). The median is therefore near zero, and a median bar called a clip with
**2 views in 3 hours** "good" — measured 2026-11-09. "Good" has to mean "doing as
well as the clips worth making more of", so the bar is the upper quartile: on
2026-11-09 that was **2.2 views/hour** for dharma (≈7 views in 3 h).

### Where the numbers come from

- **Fresh check (the 2-3 h one):** the Data API `videos.list` `viewCount`, which
  updates within minutes.
- **Fallback:** the Analytics API — a *separate* quota that survives when the
  shared Data API pool is spent (measured: Data API 403 while Analytics returned
  rows). It lags 1-2 days, so it can grade the older clips even when it cannot see
  the last one.
- When neither can see the last post, the verdict is `unknown` → the loop **keeps**
  the current shape. It never invents a grade and never breaks the publish rail.

## Making it work on the existing clips

`posted_at` is only recorded for Shorts uploaded after 2026-11-09, so the clips
already live had no clock and `gate` could not space them.
`scripts/backfill_posted_at.py` stamps `posted_at` from the manifest's git history
(the commit that first introduced each `video_id`). It is one-time and idempotent;
it needs full history, so it was run locally and the result committed — CI checks
out one commit.

## Guards

- `scripts/test_pace.py`: the gap (1 h refused, 3 h allowed), the shape flip
  (good keeps, bad flips), the bar (unknown below the baseline, splits at the top
  quarter), an end-to-end grade from real counts, and the wiring (publish records
  `posted_at` and calls pace; foreman posts one).
- `scripts/test_publish_shorts_cap.py`: now also fails if the foreman dispatches
  more than one Short per run.

Full suite: **28/28**.
