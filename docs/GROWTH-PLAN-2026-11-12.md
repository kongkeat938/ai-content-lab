# Growth plan — from measured data + panel (2026-11-12)

Back-office analysis while the rails wait for the 08:00Z quota window. Sources: the counter
ledger (`docs/counters.jsonl`), the 28-day watch-hours history (`docs/watch_hours.json`), the
video reviews (`docs/REVIEW-ch*.md`), the cached insights, and a 4-advisor panel
(`docs/PANEL-2026-11-12-growth.md`, brief `docs/CONSULT-2026-11-12-growth.md`).

## The measured picture

- **YPP long-form watch-hours (28 d):** genx 1.3 h, **dharma 44 h**, kongkeat 0.5 h.
  **dharma = 96% of all qualifying watch time.** (Shorts do not count toward the 4,000 h bar.)
- **Retention@2:00 (the binding lever):** dharma **28.9%** (target ≥ 40%). genx/kongkeat have
  no long-form with enough views to measure.
- **Subs:** genx 189, dharma 111, kongkeat 11.
- **Daily growth (ledger):** dharma spiked **+8,856 views / +42 subs** in one day (11-09→10);
  kongkeat **+3 views/day, 0 subs** for ~3 days (dead); genx grows on Shorts views only.
- **Watch-time per view (the counter-intuitive one):** dharma's 120-min video (5% completion)
  yields **~6.0 min/view**, its 17-min video (27% completion) only **~4.6 min/view**. The long
  video is the watch-hour engine; the percentage is a distraction.

## Panel (unanimous, 4/4 valid)

1. **Highest-return lever = lift the first-2-minute retention** (b), then more 60–120-min
   videos (a), then packaging (d); **do not** chase the Shorts→long funnel (c).
2. **kongkeat: pause it** — least harm; move the effort to dharma. Pivoting it now is waste.
3. **What NOT to do:** (i) do not cut dharma videos short to raise the completion % (it lowers
   total watch-time); (ii) do not try to convert genx Shorts views into long-form hours; (iii)
   do not pour effort into kongkeat.

## Plan (least harm, most gain)

1. **Concentrate on dharma.** It is the only channel earning qualifying hours and the only one
   with a real retention number. Keep its 60–120-min cadence and feed it the learned themes.
2. **Treat retention@2:00 as the headline KPI** (already measured by `analytics.py --retention`,
   shown in `docs/PROGRESS.md`). Every new dharma long-form is judged on whether it moves 29%
   toward 40% — not on views.
3. **Pause kongkeat** at the rail level (stop the weekly ch4-longform + its Shorts) until dharma
   is well past 1,000 subs; keep its assets. *(Needs a per-channel pause flag — a code change,
   proposed, not yet built.)*
4. **Keep genx as a subscriber pump only** (its Shorts grow subs fastest); expect ~0 hours.

## One concrete experiment to lift retention (needs approval)

The panel's #1 lever is the opening. The final mux applies a **4-second fade-in** to the whole
file (`make_night_video.py` / `make_chapter_video.py`: `afade=t=in:st=0:d=4`), which also fades
in the **spoken hook** — counterproductive when 71% leave within 2 minutes. It is a tested
invariant (`test_night.py`), kept so a replay loops cleanly.

Proposal: cut the fade-in to **1 s** (the tail fade-out, which actually creates the seamless
loop, is unchanged) and measure **retention@2:00** over the next 2–3 dharma long-forms. If it
rises, keep it; if not, revert. This is a one-line change but it alters a shipped rail, so it is
**proposed, not applied** — it must be verified by the retention number, never by a doc.

## Corrections found while analysing

- **Stale memory corrected:** the note "the fingerprint does NOT include the hook file" is
  **false now** — `night-compilation.yml` (line 115) hashes `content/hooks/dharma.md` into the
  fingerprint, so a hook edit **does** trigger a rebuild. (genx/ch4 longform likewise.)
- The retention KPI is **live**, not dark: `docs/watch_hours.json` carries
  `retention_2min = 28.9` for dharma; `docs/PROGRESS.md` renders it. genx/kongkeat show `—`
  because no long-form there has enough views to measure — correct, not a bug.
