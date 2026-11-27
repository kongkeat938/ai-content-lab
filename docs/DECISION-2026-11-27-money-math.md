# DECISION 2026-11-27 — the money math, measured

Written by `ak` after K's "ลุยเลย ไม่ต้องกลัวผิด" (2026-11-27). Every number below was read from the
live YouTube Data API at **2026-11-27 16:00 UTC (23:00 Thai)** or from a CI log named in the row.
Nothing here is a projection unless it is labelled *ประมาณ*.

## 1. The three channels, live

| channel | videos | subs | lifetime views | Shorts | median views/Short | Shorts ≤5 views | views in last 21 d |
|---|---|---|---|---|---|---|---|
| genx (ch1) | 182 | 203 | 42,915 | 152 | 120 | 31 (20%) | 22,056 |
| dharma (ch2) | 205 | 179 | 46,003 | 181 | 101 | 63 (35%) | 36,310 |
| kongkeat (ch4) | 127 | 11 | 6,046 | 117 | **1** | 89 (76%) | 637 |

- **dharma is the only channel still being fed by the feed** (36.3k views in 21 days = ~1,730/day).
- **kongkeat is dead by measurement, not by opinion**: 76% of its Shorts never passed 5 views, and its
  best video (1,083) is older than the last 30 uploads combined. Paused 2026-11-27 (`content/PAUSED`).
- Subscribers per video: genx 1.12, dharma 0.87, kongkeat 0.09. A channel that converts under ~1 sub
  per video is not building an audience; it is publishing into a void.

## 2. Distance to the money (YPP)

YPP needs **1,000 subs + one of**: 10 M public Shorts views in 90 days, or 4,000 public watch hours.

| route | have | need | at the current rate |
|---|---|---|---|
| Shorts views / 90 d | dharma ~155 k (*ประมาณ*: 36.3 k × 90/21) + genx ~95 k | 10,000,000 | **~2.5% of the bar**, ~6 years at this pace |
| subscribers | 382 combined (203 + 179) | 1,000 | ~+2/day observed → ~10 months, if it holds |
| watch hours | **not measurable** — the Data API has no watch-time field, and the Analytics API scope is not in our token | 4,000 | unknown, do not guess |

**Conclusion (the uncomfortable one):** ad revenue is not a near-term income path. At 2.5% of the
Shorts bar, "make more Shorts" changes nothing about when money arrives. The factory is fine; the
distribution is the wall.

## 3. What the data says about the product (age-controlled, views/day)

| finding | n | evidence | confidence |
|---|---|---|---|
| Shorts longer than ~48 s die | 67 vs 266 | median **8 views** (n=67) vs 142–201 for 33–48 s; holds inside the วิธี theme (0.19 vs 7.17 v/day) and the rest theme (0.36 vs 10.79) | **strong** for "do not ship >48 s", **not** proof of the cause (older clips came from an older builder — era confound) |
| Titles longer than 55 chars do better | 14 / 46 | dharma 17.4 vs 6.1, genx 14.1 vs 6.2 | weak–moderate |
| "ก่อนนอน" in the title does *worse* | 135 | 5.2 vs 16.0 v/day | confounded by theme mix — do not act yet |
| A title with a number does better | 8 | 26.5 vs 6.2 v/day | too small to act |

The only test worth running is the duration one, and it must be run as an A/B, not a rebuild:
20 Shorts at 28–32 s vs 20 at 45 s, same theme, same hook pool, compare first-week views.

Pooled over both live channels and controlled for theme (2026-11-27, n=333 Shorts), the >48 s group is
not weak — it is dead: median 8 lifetime views against 142–201 for everything at 33–48 s, and the newest
48.7 s clip still opened at 87 views/day, so the bar is not "48 s exactly". Until the A/B runs, the
production rule stays 30–45 s (the gate already allows ≤60 s; this is a target, not a gate).

### 3b. The same test inside one era (2026-11-28, so the claim is not an age artefact)

Lifetime views flatter the newest clips, so the >48 s group was re-measured among clips **posted in the
same recent window** (posted_at from the manifest, views/day from the live API):

| window | ≤48 s | >48 s | ratio |
|---|---|---|---|
| last 21 days | n=110, median **14.69 v/day** | n=27, median **7.63 v/day** | 1.9x |
| last 12 days | n=34, 27.43 v/day | n=7, 7.03 v/day | 3.9x |
| last 7 days | n=20, 61.74 v/day | n=5, 7.03 v/day | 8.8x |
| dharma, 21 days | n=57, 24.85 v/day | n=11, 7.35 v/day | 3.4x |
| genx, 21 days | n=53, 10.35 v/day | n=16, 8.28 v/day | 1.25x |

**Honest read:** the direction survives the era control — it is not only "old clips were long". But the
lifetime figure (8 vs 142–201) overstates the gap; inside a single era it is **1.9x pooled, 3.4x on
dharma, and thin on genx (1.25x, n=16)**. The claim to keep is "prefer 30–45 s"; the claim to drop is
"a 49 s clip is worth 5% of a 40 s clip". The A/B above is still what would settle it.

Because the rail can now predict a clip's length from its script (`content/duration_calibration.json`,
R²=0.956, n=241), it publishes the short end of the pool first on dharma and genx — a sort, not a gate,
so a long clip still goes out when the short ones run out.

## 4. What we cannot measure (say so, do not invent)

- **Watch time / average view duration** — needs the YouTube Analytics API; our OAuth scope is Data API only.
- **First-24 h views** — no time series; `views/day` mixes the initial burst with the long tail.
- **Whether any clip already on YouTube is 4K** — no local copies and the API reports only `definition: hd`.
  What *is* proven is the factory: CI logs show `2160x3840 yuv420p tv bt709 lufs -14.2` for Shorts and
  `3840x2160` for long-form.

## 5. The four money paths, ranked by speed to the first 5,200 THB

| path | what exists today | evidence of demand | blocker | verdict |
|---|---|---|---|---|
| **A. Sell the factory as a service** (`docs/OFFER-2026-11-25.md`) | offer + prices + 12 measured prospect channels + 2 demo releases | **none yet** — the pack has never been sent | sending it needs K's hand (or explicit approval for ak to send) | **fastest plausible cash**: one 5,000 THB job = the whole monthly gap |
| **B. Freelance marketplaces** (`content/prospects_external.json`) | 126 open requests, budgets $11–137, refreshed daily by `prospect-daily.yml` | real requests, real budgets | needs a freelancer.com account with ID verification + competitive bidding; 126 leads ≈ 126 pitches | real but small: $60 ≈ 2,100 THB, one-off |
| **C. Affiliate** | nothing built | unknown | needs an affiliate account (approval) and traffic we do not have | pennies at 1.7 k views/day — **skip for now** |
| **D. YouTube ads** | 2.5% of the Shorts bar | n/a | years at the current rate | keep producing, do not count on it |

**Decision: A is the path, B is the fallback, C is parked, D is a by-product.**
The bottleneck is not code — the repo already has 232 scripts, 134 tests and 39 workflows. It is
**someone sending the offer**. That is the only "system" that is missing, and it is a human action.

## 6. 30-day plan (0 THB, measured weekly)

| week | action | success measure | stop rule |
|---|---|---|---|
| 1 | send the offer to 20 of the 12 measured prospects + 8 more; keep a reply log | 20 sent, ≥1 reply | 0 replies from 20 → the offer text is wrong, not the market; rewrite once |
| 2 | deliver one paid job at cost (or a free sample to one prospect) | 1 delivery, ≤3 h of human time | if a delivery eats >8 h, the factory is not ready to sell |
| 3 | run the 28–32 s vs 45 s A/B on dharma (20 + 20) | first-week views compared | no difference → drop the duration rule, keep 40 s |
| 4 | decide: keep selling (any cash) or stop the sales track | ≥1 paid job or ≥3 warm replies | 0 cash and 0 warm replies after 30 days → stop the sales track, keep publishing as a by-product |

Guard rails that stay: 0 THB spend, `content/PAUSED` for ch4, the upload gates (4K, no-repeat),
`DAILY_CAP=3`, and no publish that fails a gate that can FAIL.

## 7. What today's bug hunt cost and taught (so it is not paid for twice)

1. `fetch-depth: 1` + `git pull --rebase` = **exit 128** → the id was lost *after* the upload; three live
   Shorts read as "rogue uploads" (run 45976910714).
2. After fixing that, the in-run commit *still* failed: the run's own ledger writes kept the tree dirty
   (`You have unstaged changes`). Fixed by staging `content/` with the manifest.
3. A guard that cannot fail proves nothing: `test_manifest_push.py` fails 4/13 with the staging line
   removed, and that failure is exactly production's symptom.
4. One channel name was not enough to pause a channel: `content/PAUSED` needs **both** `kongkeat` and
   `kongkeat-story`; with one, `publish_shorts.py --channel kongkeat` still ran.

Pending proof: the in-run commit has not yet been seen succeeding in production — the 15:32 UTC run
deferred on the pace gate (`only 0.4h since the last post (need 2.0h)`). Next eligible post **00:07 Thai**;
check that log for `manifest committed`.
