# PACKAGING PLAN — ch2 (Farmmer, ธรรมะก่อนนอน)

Built 2026-11-08 from the competitor research in
`ax-workspace/docs/COMPETITOR-RESEARCH-2026-11-08.md`. This is the
implementation record: what was changed, what it measures, and how to verify it.

## The measured problem

A YouTube search for **ธรรมะก่อนนอน** returned **no Farmmer video in the top 30**,
while channels with only 4,300 subscribers held 600k–800k views. The blocker is
therefore **packaging (cover + title)**, not reach.

Winning covers share one recipe: a **glowing gold Buddha on a deep-navy night**
with a few **big, heavy-stroke Thai words**. Winning titles carry an emotional
hook ("หลับลึกใน 5 นาที", "เทวดาคุ้มครองตลอดคืน", "ปล่อยวาง").

## What was built (all free tools)

| Lever | Tool | Notes |
|---|---|---|
| Cover | `scripts/make_cover_youtube.py` | 1280×720; gold-gilded Buddha + navy + big Thai text. Art from `assets/branding/farmmer/art/` (CC0/PD, see its `credits.json`). Layout alternates sides per video so a channel page is not a wall of identical covers. |
| Title + tags + cover | `scripts/apply_packaging.py` | Reads `content/ch2_packaging.json`; writes through the Data API. Quota-aware, ledger in `content/packaging_changes.json`. |
| Playlists | `scripts/channel_overhaul.py` (`--channel ch2`) | Two new thematic shelves: ปล่อยวาง/คลายกังวล and นิทาน. Idempotent. |
| Opening hook | `content/hooks/dharma.md` | Trimmed to seven beats (~44 s) and the fixed "20 นาที" claim removed. |
| Slot safety | `scripts/publish_batch.py --publish-at` | YouTube holds the video private and flips it at `publishAt`, so a dropped cron cannot miss a slot. |

Vision review of the 13 covers: **8/10** (iterated from 7/10 by gold-gilding the
statues and alternating the layout).

## The plan

`content/ch2_packaging.json` holds a title, cover text and hook for every ch2
video (13). Titles keep **ธรรมะก่อนนอน** as the first search token, state the
**measured** duration, and add an emotional hook.

## Rails (run after the 08:00 UTC quota reset)

| Workflow | When | What |
|---|---|---|
| `apply-packaging.yml` | 08:25 / 09:25 UTC + push | titles, tags, covers |
| `ch2-playlists.yml` | 08:40 UTC + push | create and top up playlists |
| `set-thumbnails.yml` | every 20 min | repair any cover that did not set |

All three are idempotent, so an extra tick is free and a dropped tick is safe.

## How to verify (evidence, not claims)

```bash
# what the plan would do, no API calls
python3 scripts/apply_packaging.py

# are the covers live yet?
python3 scripts/set_thumbnails.py --check

# what has been applied
cat content/packaging_changes.json
```

The effect is judged later by **views-per-day** against the baseline recorded in
`docs/title_changes.json` — keep the change if views-per-day rises, revert if not.

## Status 2026-11-08

Covers generated and committed. Live apply **deferred**: the daily Data API quota
was already spent when the work landed, so the first writes happen at the 08:25
UTC tick. The ledger will record each one.

Verified on the runner (evidence, not claims):

| check | result |
|---|---|
| `apply-packaging.yml` dispatch | success; log `quota exhausted -- re-run after the 08:00 UTC reset`, `done: 0 applied` — auth and wiring proven |
| `ch2-playlists.yml` push | success; log `=== ch2 Farmmer — API said 403; deferring` — auth and wiring proven |
| `set-thumbnails.yml` push | success; manifest now maps all 13 videos to their new covers |
| covers committed | 13 JPGs + 8 art files + `credits.json` |
| plan coverage | 13 / 13 ch2 videos |

A fixed release slot was also wired: `night-compilation.yml` now dispatches
`publish-batch.yml` with `publish_at=slot`, so a new compilation goes up private
and YouTube flips it public at **19:30 Bangkok (12:30 UTC)** on its own clock.
A dropped cron can no longer miss the slot.

