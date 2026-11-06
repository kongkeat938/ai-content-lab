# Effect read — titles + thumbnails + SEO (measured 2026-11-06 14:30Z)

K asked to pull the reports and read the effect. The honest answer right now is
**the effect cannot be read yet** — and this file records why, so the +14-day read
is not fooled the way the first naive attempt almost was.

## The honest verdict

**No effect can be claimed.** The changes were applied 1-2 hours before this read
(12:27-14:02Z) and the YouTube Analytics API lags about **3 days** — today is
2026-11-06 and the newest analytics day is **2026-11-03**. There is no post-change
window yet. Any "+341%" style number computed today is noise.

## A wrong read, kept as a warning

A first pass reported `+341%` / `+60%` on the ledger baseline and `271x` against the
pre-change rate. **That was thrown away.** Two defects:

1. The ledger's changed set mixes **Shorts** (feed-driven, hundreds of views an
   hour) with long-form, so the delta measured the Shorts feed, not the metadata.
2. The baseline was captured at posting time, so the delta was mostly the video
   getting older.

`scripts/measure_changes.py` now excludes Shorts (duration > 180s) and compares a
fixed pre-window against a post-window, with an optional control group.

## What the data does say today

**Traffic is 91-97% Shorts feed; YouTube search is 1.5-2.0%** (28 days):

| channel | total views | SHORTS | share | YT_SEARCH | share |
|---|---|---|---|---|---|
| genx | 5,751 | 5,511 | 95.8% | 89 | 1.5% |
| dharma | 7,027 | 6,370 | 90.7% | 127 | 1.8% |
| kongkeat | 3,709 | 3,598 | 97.0% | 74 | 2.0% |

The metadata changes only touch the **1.5-2.0%** search surface (plus the browse
and related rails). A realistic ceiling on the effect is therefore small relative
to the Shorts feed — which is exactly why the long-form titles/thumbnails/SEO were
the right lever (they own the surfaces that are not the feed), but also why a big
number should not be expected.

**Long-form is genuinely tiny** — pre-change baseline, 2026-10-23..11-05:

| channel | long-form videos | views in 14d | per day |
|---|---|---|---|
| genx | 17 | 78 | 5.6 |
| dharma | 8 | 164 | 11.7 |
| kongkeat | 4 | 12 | 0.9 |

That is the real problem: **not the metadata, the long-form volume.** Metadata can
only multiply a small base.

## Provisional live read (not evidence)

Live `viewCount` since the change, ~1 hour in: genx +0, dharma +16, kongkeat +3.
Too short and too small to mean anything; recorded only so the +14-day read has a
starting point.

## The plan for the real read

At **2026-11-20** (14 days after), run:

```
python3 scripts/measure_changes.py --channel genx --control
python3 scripts/measure_changes.py --channel dharma --control
python3 scripts/measure_changes.py --channel kongkeat --control
```

Baseline captured in `docs/measure_baseline.json`. Compare per-day views of the
treated long-form set against its own pre-window; keep what rises, revert what
does not. Until then: **no claim.**
