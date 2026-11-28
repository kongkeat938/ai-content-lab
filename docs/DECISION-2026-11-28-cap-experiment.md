# DECISION-2026-11-28 — two posts a day instead of three, run as an experiment

K: *"อยากทำไร ทำเลย เราเก่งอะไร ค้นหาอะไรที่ใช่สำหรับ ak ทำเลย มันต้องสำเร็จสักอย่างจนได้แหล่ะ"*

ak's edge is not opinions, it is measurement → change → measure again. So this round measured the
two things that decide whether the channels earn anything, and shipped the one change the data
supports.

## 1) Where the channels really are (live, 28 days, YouTube Analytics API)

| channel | views | watch-hours | of which long-form (YPP-qualifying) | Shorts | subs +/- |
|---|---|---|---|---|---|
| dharma | 48,207 | 237.8 h | **81.9 h** | 155.9 h | +185 / -10 |
| genx | 43,048 | 187.1 h | **14.5 h** | 172.5 h | +205 / -10 |

Subs now: dharma 178, genx 204.

**The hard number nobody wants to say out loud:** YPP needs 3,000 watch-hours of
long-form-shaped content (or 4,000 in 12 months) and 1,000 subs. At 81.9 h / 28 days, dharma needs
**~34 months**; at 14.5 h, genx needs ~16 years. Subs arrive at ~190/month → ~5 months. So **ad
revenue is not a 2026 outcome**; Shorts monetisation (10 M views / 90 days) is further still
(91 k views / 28 days today).

That is the honest frame: the channels are a **portfolio and a proof**, not the income. The income
is selling the engine — and that is blocked on one human step (a seller account), not on code.

## 2) The one thing ak can move alone: how much each post is worth

Measured 2026-11-28 from the live API + the manifests (245 Shorts with a `posted_at`):

| window | <=48 s | >48 s | ratio |
|---|---|---|---|
| last 21 days | 14.69 v/day (n=110) | 7.63 (n=27) | 1.9x |

and, new this round, **posts per day** (era-controlled: clips posted in the same week only):

| week (ISO) | days with 1–2 posts | days with 3+ posts |
|---|---|---|
| 2026-W45 | n=2, 5.23 v/day | n=19, 0.77 |
| 2026-W46 | n=20, 17.62 | n=9, 4.29 |
| 2026-W47 | n=12, 14.89 | n=12, 14.88 |
| 2026-W48 | n=13, 92.89 | n=3, 151.60 |

Per-week medians: **16.26 (1–2 posts) vs 9.59 (3+ posts)**; fewer posts won in **3 of 4 weeks**
(n=90 clips). The third post of a day is worth less than the slot it costs — the same shape as the
2026-11-05 flood, just milder. n is small (4 weeks), so it is run as an experiment, not a new law.

## 3) The experiment (7 days, zero cost, no code risk)

- **Arm:** dharma, `"daily_cap": 2` (2 posts / 24 h).
- **Control:** genx, shared ceiling 3 — unchanged, so both arms differ by exactly one setting.
- **Baseline (7 days before the switch):** dharma's clips posted in the last 7 days had a median of
  **~61.7 v/day** (n=20); genx ~7-10 v/day.
- **Measure after 7 days:** median views/day of the clips posted during the window, per channel,
  plus the channel's daily views from the Analytics API (the number that actually matters).
- **Keep it if:** dharma's median views/day ≥ **1.3x** its own prior-7-day median **and** channel
  daily views did not fall. Then apply the same cap to genx.
- **Revert if:** the median falls, or channel daily views fall for 3 days running. Reverting is one
  line (`"daily_cap"`) and the guard sweeps every channel, so no rail is left half-changed.

## 4) Why this and not something bigger

- YPP: measured above, out of reach this year — no amount of rail work changes the arithmetic.
- Affiliate / digital products / freelance platforms: every one needs an account with a phone number
  or a payout account in K's name. ak cannot create those and must not pretend to.
- More systems: the repo already holds 263 scripts and 132 guards; the bottleneck is not tooling.
  A new rail would be another thing to maintain, not another view.

So the only lever ak owns alone is **the value of each post**, and the only thing that turns that
into money is K's 15 minutes on the seller account (`docs/FASTWORK-LISTING-2026-11-27.md`).
