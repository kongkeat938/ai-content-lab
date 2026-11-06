# Watch-hour measurement — 2026-11-06 (the revenue lever, verified)

Measured with `scripts/analytics.py` (YouTube Analytics API, 28-day window
2026-10-09 .. 2026-11-06). The Analytics endpoint has its own quota, so this
reads even on a day the Data API (10,000 units) is spent.

## Headline

| channel | views 28d | watch-hours 28d | subs +28d |
|---|---|---|---|
| genx | 5,743 | 24.2 | +20 / -1 |
| dharma | 7,018 | 39.4 | +23 / -1 |
| kongkeat | 3,695 | 15.5 | +8 / -0 |
| **total** | **16,456** | **79.1** | **+51** |

Against the 2026-10-31 baseline in `docs/FAST-REVENUE-PLAN.md` (watch-hours
28d = **30.1**, views 28d = 8,309): watch-hours are up **2.6x** and views up
**~2x** in under a week. Part of this is the subscriber/views surge K noticed;
part is the metadata pass. The 14-day read is what decides.

## The lever is confirmed: the 120-minute compilation

Per-video breakdown, dharma, by watch-hours:

| video | views | watch-h | avg% | note |
|---|---|---|---|---|
| `F4qFHoVpEyI` | 146 | **8.72** | 4.6% | **night_120** — the 120-min compilation |
| `oyrWvxdnImY` | 1,236 | 2.87 | 114.9% | Short, loops |
| `oIsloIKa0J4` | 1,292 | 2.70 | 56.3% | Short |
| `AANBJpLDpUc` | 358 | 1.40 | 274.3% | Short, loops |
| `wIpNM1gqPYc` | 1,083 | 1.12 | 42.2% | Short |

**`F4qFHoVpEyI` alone is 8.72 / 39.4 = 22% of all dharma watch-hours, from one
video.** Its ratio is 8.72 / 146 = **0.0597 watch-hours per view** — the 0.060 the
plan predicted, to three digits.

The Shorts at the top of the list have *more views* (1,236 vs 146) but *less*
watch time (2.87 vs 8.72). That is the whole argument for the long-form rail in
one table: a view is not a watch-hour, and the 120-minute file earns them.

`night_110`, `night_money_01` and `night_sleep_01` are not in this window — they
went live 2026-11-05/06, after it. Their contribution shows up in the next read.

## What this changes

* Keep the long-form rail as the primary watch-hour engine; the autopilot
  (`docs/LONGFORM-AUTOPILOT-2026-11-06.md`) is the right investment.
* The Shorts still earn reach and subscribers (subs +51 in 28 days), so they stay
  — but they are the funnel, not the monetization.
* Judge the metadata pass at **14 days** (`docs/EFFECT-READ-2026-11-06.md`), not
  from this 28-day window, which mixes in the surge.

## Fix applied

`analytics.py --videos` used to fail entirely when the Data API quota was spent,
because it resolved titles through that API and let the 403 abort the report.
Now the per-video rows (Analytics quota, separate) print even when the titles do
not, and the channel total is never lost to a title lookup.
