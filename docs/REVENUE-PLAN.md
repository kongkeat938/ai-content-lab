# REVENUE PLAN — ch2 Farmmer ธรรมะก่อนนอน

Written 2026-11-03 by ak, under K's standing order to run this as a business.
Every number here is measured, not assumed. Where it conflicts with generic advice,
the measurement wins and says why.

## Where the money comes from

YouTube pays through the **Partner Programme**: 1,000 subscribers **and** 4,000
public watch hours in 12 months (or 10M Shorts views in 90 days). Below those
thresholds YouTube pays nothing, so the plan is: **reach the threshold fastest,
then monetise.** Secondary income can start before the threshold.

## The measured starting point (2026-11-03)

| | ch2 Farmmer |
|---|---|
| subscribers | 11 |
| views (28 d) | 4,185 |
| watch hours (28 d) | 8.5 |
| subs per view | 0.26% (healthy ≈ 1%) |
| Shorts 14–26 s | 1,290 / 1,237 / 1,081 / 334 / 317 views |
| long 12–16 min | 1 / 2 / 5 views |
| **new: long 120 min** | `F4qFHoVpEyI`, public, 2026-11-03 |

Two facts drive everything:

1. **Shorts get views; the old long clips got none.** The Shorts reached 1.2k; the
   12–16 min clips reached single digits. Discovery lives in Shorts.
2. **Watch hours need long videos.** 4,000 hours is the hard gate. A 120-minute
   video watched even part-way banks far more hours per view than a 3-minute one.
   Competitors in this niche ship **82–240 minutes** (measured) for exactly this.

So the engine is **Shorts for reach, long videos for hours** — not one or the other.

## The plan

1. **Ship a long video regularly, in the niche's winning length.** 120 min is live;
   the 110-min one publishes 2026-11-05 (held for cadence). Keep the 2-hour rail fed.
2. **Drip Shorts daily.** 7 live; the pool holds 20 and grows nightly via Gemini.
   Each Short's description links the 120-minute video — that is the funnel.
3. **Fix the follow rate.** 0.26% subs/view is the real defect. Every Short already
   ends with a spoken CTA; the long video's description and pinned comment ask too.
4. **Thumbnails on every long video.** A 0.26% channel lives or dies on CTR. Rail is
   built (`set_thumbnails.py`); blocked only by the shared API quota, which resets
   08:00 UTC.
5. **Cross-post Shorts to Facebook / TikTok / IG Reels** with a link back. Free, and
   it borrows an audience that already exists. **No view-buying** — it violates ToS
   and YouTube suppresses the channel.

## Income before the threshold (do not wait for 1,000 subs)

- **Affiliate links** in long-video descriptions: sleep/health products, dharma books
  (Shopee/Lazada affiliate). Works at any subscriber count.
- **Donations**: a PromptPay QR in the description of the long videos, for people who
  play them all night.
- **Digital product**: a wallpaper / chant PDF, sold cheap via a Line OA link.

These are honest, low-effort, and legal. They are *secondary*: the threshold is the
prize, and everything above is worth little until the channel is monetised.

## What I am NOT doing, and why

- **Not stopping the 120-minute videos**, despite the advice to cut to 20–30 min. The
  measurement says the opposite for *this* niche: the winners ship 82–240 min and the
  short long-form clips got 1–5 views. Length is the format here.
- **Not buying views or subscribers.** ToS violation; YouTube suppresses the channel.
- **Not spinning up new Google accounts** to dodge limits (a standing repo rule).

## Honest expectation

At 0.26% subs/view, 1,000 subs needs ~380,000 views; at the current ~4k views/28 d
that is far off. The lever is **views per Short** and **follow rate**, not more
upload slots. If a Short breaks out (a 100k Short is normal in this niche), the plan
accelerates; if none does, the format or the hooks are wrong and the scripts change.
Watch `subs per view` — it is the single number that says whether this is working.

## To check it is working (weekly, measured)

- subs per view — target ≥ 0.5%, then ≥ 1%
- Shorts median views — is any Short breaking out?
- long-video watch hours — the number the threshold counts
- clicks Short → long (if analytics ever becomes readable; tokens lack the scope today)
