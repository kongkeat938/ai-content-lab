# Panel — ch4 recovery, after the unpause (2026-11-13)

Five-advisor panel (`scripts/advise.py --broad`). 4/5 answered (gemini-3.5-flash:
HTTP 429). Question: after unpausing ch4, what is the highest-leverage next move for
YPP long-form watch-hours, and which single defect to hunt next?

## Facts put to the panel (all measured)
- ch4 paused 2026-11-12: a flat "warm scene" hook held **13.7%** mid-retention
  (genx/dharma tension hooks 62–68%).
- Unpause found a second defect: the pause had removed kongkeat from the
  `matrix.include` of publish-shorts / grow-shorts-pool / remake-shorts, so new
  Shorts could never publish. Fixed; `test_rail_channels.py` now guards the
  invariant "in matrix ⟺ not in content/PAUSED".
- 7 new Shorts scripts (ids 97–103) pass the rail's tension filter; 74/101 older
  scripts are flat and held back.
- ch4 subs/1,000 views = 1.93 (worst on the fleet); the pinned CTA comment — the
  only CTA that shows on the Shorts screen — was missing on ch4.

## Verdict (unanimous)
1. **Highest-leverage move = the Shorts → long-form bridge.** Watch-hours come from
   long-form only, so every new Short must funnel to the long video/playlist
   (related-video link + pinned comment). Do not spend slots re-posting the flat
   scripts — bad reach drags channel authority down with it.
2. **Next defect to hunt = "tension leakage" in the long-form itself.** A flat
   middle (roughly minutes 2–5) would reproduce the 13.7% failure inside the file
   that earns the hours; scan the long-form for a flat stretch the same way the
   Shorts pool is scanned for a flat hook.
3. **Do not unpause before the wiring is verified 100%** (the panel named this
   independently, and it is exactly the matrix-drop defect that was measured here).

## Actions taken from the verdict
- ch4 `pin_cta` added → the durable ch4 playlist (`PLU4aztRNvt28`, measured live to
  hold the channel's long videos); guard now sweeps every channel, not a hardcoded pair.
- To measure next: whether the pinned funnel lifts ch4 subs/1k, and whether the new
  long-form's mid-retention beats 13.7% (the counter, not a claim).
