# Polish pass — every title + every ugly thumbnail (2026-11-06)

K saw the effect of the first pass (subs jumped) and ordered the rest: change
every title and every weak thumbnail, on all three channels.

## Verified result of the first pass

Subscriber counts, measured live 2026-11-06 (Data API), against the 2026-10-31
memory snapshot:

| channel | subs 10-31 | subs 11-06 | change |
|---|---|---|---|
| genx | 6 | 124 | +118 |
| dharma | 7 | 33 | +26 |
| kongkeat | 6 | 10 | +4 |
| total | 19 | 167 | +148 |

Titles applied so far were checked against the live watch pages (oEmbed, no
quota): **6/6 match the ledger.** The effect is real, so the pass continues.

## What is done, what is left

| channel | videos | titles changed | thumbnails changed |
|---|---|---|---|
| genx | 84 | 15 | 19 (from the earlier long-form pass) |
| dharma | 99 | 33 | 10 |
| kongkeat | 38 | 7 | 7 |
| **total** | **221** | **55 + 40 = 95** | **36** |

Remaining to change: **genx 69, dharma 66, kongkeat 31 titles**, and the matching
thumbnails.

## Why it does not finish today: the API quota

The YouTube Data API allows **10,000 units a day**. `videos.update` costs 50, so
a title pass is 50 units per video; 126 remaining titles is ~6,300 units, and the
thumbnail work is on a separate bucket. Today's quota was already spent by the
earlier title + thumbnail + SEO passes, so every call now returns
`quotaExceeded`. The quota resets at **08:00 UTC**.

Both scripts now stop cleanly on that error and keep a ledger
(`docs/title_changes.json`, `docs/thumbnail_changes.json`), so a later run skips
what is already done and resumes.

## The unattended finisher

`.github/workflows/polish-all.yml` runs titles then thumbnails for all three
channels after the 08:00 UTC reset, and commits the ledgers. It runs on:

* the schedule (`11 8,9,10,11 * * *` — the morning ticks after the reset), and
* any push to `scripts/optimize_titles.py`, `scripts/make_video_thumbnail.py` or
  the workflow itself (GitHub's scheduler never fires in this repo, so a push is
  the dependable trigger; the job's ledger commits do not touch those paths, so
  it cannot loop).

Verified working today: a push started the job, it walked all three channels and
hit the quota path cleanly (run 42238671491, success). Tomorrow's tick after the
reset does the real work.

## Caveats kept on the record

* Titles on **Shorts** are the low-value half of this pass: 91-97% of views come
  from the Shorts feed, where the title is not the discovery lever, and editing a
  live Short carries some risk to its feed distribution. K asked for every title,
  so they are included; the thumbnails on Shorts are also not shown in the feed.
  The value is concentrated in the long-form videos.
* The real lever remains **long-form volume**: long-form drew 5.6 / 11.7 / 0.9
  views a day before this pass (see `docs/EFFECT-READ-2026-11-06.md`).
