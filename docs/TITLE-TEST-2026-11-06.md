# Title-change test — first read (2026-11-06)

Question from K: after 11 titles were rewritten, how many minutes have passed, did
the views move, and if they moved meaningfully, do more.

## What the clock says

The 11 changes were applied 12:27–12:29Z on 2026-11-06. Read at 13:25Z, so about
**57 minutes** had passed. One hour is far too short to judge a title.

## What the numbers say

Per video, before (views per day since upload) against after (views per day since
the change):

| video | base views | now | before/day | after/day |
|---|---|---|---|---|
| N6IyyBdoM-Q | 22 | 28 | 555 | 145 |
| 4bDxO7b6IjM | 0 | 4 | 0 | 97 |
| RZk1coq-xyQ | 79 | 108 | 642 | 700 |
| k4YWsVDhV3c | 2 | 4 | 124 | 50 |
| IZCnSGwqXGY | 1 | 6 | 60 | 124 |
| Q_MUoXffHDs | 19 | 48 | 152 | 722 |
| 7-4m2Kop9w4 | 51 | 70 | 305 | 473 |
| dmUf63_CT64 | 6 | 12 | 58 | 150 |
| 4-dK-yKz_DM | 0 | 0 | 0 | 0 |
| 3nGouuTkySM | 0 | 0 | 0 | 0 |
| 8Xiq1ganmRs | 0 | 0 | 0 | 0 |

Aggregate before 1,897/day, after 2,461/day (x1.30). Total +290 views in 57 min.

**That x1.30 is not a real effect.** The per-video ratios run from 0.26 to 4.74 --
the direction flips video to video, which is what noise looks like, not what a
title effect looks like. And the channel's own recent days swing far more than
that on their own (measured: 2026-11-01 344 views, 2026-11-02 588, 2026-11-03
3,130) because a Short was fed by the Shorts feed. +290 in an hour is inside that
normal swing.

## Why the title cannot be the cause: the traffic is not search

Measured with the Analytics API (`insightTrafficSourceType`, last 7 days):

| channel | SHORTS feed | YouTube search | everything else |
|---|---|---|---|
| genx | 5,511 (98.4%) | 84 (1.5%) | ~120 |
| dharma | 6,370 (93.9%) | 125 (1.8%) | ~290 |
| kongkeat | 2,786 (96.9%) | 71 (2.5%) | ~20 |

**93-97% of every channel's views come from the Shorts feed, and only 1.5-2.5%
from search.** Of the 11 changed videos, **10 are Shorts** (40-54 s). A Short is
shown to people by the feed regardless of its title, so rewriting its title
cannot change where those views come from. This is the decisive number, and it
says the first 11 changes cannot show a title effect -- by construction.

The one long-form video changed (`8Xiq1ganmRs`, 20 min, kongkeat) went 0 -> 0.

## Honest conclusion

- **Not meaningful.** One hour, and the videos are Shorts whose traffic is feed,
  not search.
- Do **not** add more blindly. Adding 200 more Short title changes would move the
  same 2% of traffic.
- The lever that can actually be tested is the **long-form** videos, where search
  is the discovery path. genx has 17 long-form, dharma 10, kongkeat 4 -- and they
  currently get 1-36 views each. Those are the ones worth a keyword title, measured
  over two weeks.
- Keep the 11 changes (they are not harmful) and judge them at 14 days against
  `docs/views_snapshot.json`, which holds the 60-video control baseline.
