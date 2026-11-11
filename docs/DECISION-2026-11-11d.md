# Decision — the stalled delete loop + the rogue stream (2026-11-11)

Frame: have presence of mind → order the events → find the causes → weigh
pros/cons and the effect on the goal → take the fullest data to the panel →
choose the option with the most gain and the least harm → act (no waiting).

## Timeline (measured, not claimed)

1. 2026-11-08 — the first Middle-Way dharma build (`HkbSguA53ro`) shipped: one
   static card looped for the whole 57-minute file, averageViewDuration 5.2%.
2. `remove-bad-cut.yml` was written to delete it (a Reused-Content risk), running
   after the 08:00 UTC quota reset and on every `ch2_publish.json` push.
3. The delete never succeeded. The guarded delete refuses a video above
   `--max-views 5`, and the video's views kept rising: **0 → 25 → 31 → 44 → 53**.
4. No `.done` marker is written on a skip, so the foreman kept re-dispatching it
   — **~37 attempts in one day**, each spending quota and doing nothing.
5. The intended replacement is already live under a different title
   (`night_middleway_01` = `RJPCYx_DUqU`), so the bad cut adds nothing.

## Causes

- **Immediate:** a skip rule (`views > 5`) that does not terminate the loop.
- **Root:** the only success marker (`.done`) is written on a *successful* delete,
  so a *refused* delete is indistinguishable from a *pending* one. The rail has no
  way to stop retrying a video it will never delete.
- **Contributing:** the video gained views after the decision to remove it, which
  is exactly what the safety guard was designed to catch.

## Options and effect on the goal

| Option | Gain | Harm | Goal effect |
|---|---|---|---|
| Delete (`--force`) | gone forever | irreversible; destroys a video the channel still shows | small upside, real risk |
| **Private (`--unpublish`)** | removes the Reused-Content exposure; reversible | the video still exists (invisible) | **protects YPP, nothing lost** |
| Leave public, stop the loop | none | 5.2% AVD stays public on the channel that carries **96% of watch time** | keeps a policy risk |

Goal = YPP watch-hours on long-form + subscribers, no strikes. The 53 views are
~2.6 hours and do **not** count toward the goal, but the channel is the one that
carries 96% of it — so a strike there is the costliest outcome. Private gives the
whole gain (risk removed) with no irreversible harm.

## Panel (docs/PANEL-2026-11-11d.md)

4 valid advisors (gemini-3.5-flash-lite, gemini-3.6-flash, gemma-4-31b-it,
gpt-oss-20b). **Unanimous on the shape:** stop the exposure immediately; prefer the
reversible move; do NOT delete; do NOT rotate the OAuth token before the bleeding
is stopped. 2 advisors pushed to "rotate the token now"; the majority held that
rotating kills our own pipeline (K must re-consent in a browser) and is step 2.

## Choice (least harm, most gain)

**Set `HkbSguA53ro` private (reversible) and write the `.done` marker so the loop
ends.** Keep the rogue-stream take-down (also reversible) armed for the post-reset
window. Do not delete; do not rotate the token yet.

## Execute / Verify

- `delete_video.py --unpublish` sets `privacyStatus=private` and writes `.done`
  (even when already private). `remove-bad-cut.yml` calls it.
- Guard `scripts/test_delete_unpublish.py`: dry run changes nothing; `--unpublish`
  never deletes even at 53 views; the marker is written; the rail uses it — each
  proven to FAIL when removed. Suite 36/36.
- The live unpublish runs in the post-reset window (the read quota was spent at
  14:xx UTC; the pod's whole Data API pool resets 08:00 UTC). Verify after: the
  video reads `private` and `content/deleted/HkbSguA53ro.done` exists.
