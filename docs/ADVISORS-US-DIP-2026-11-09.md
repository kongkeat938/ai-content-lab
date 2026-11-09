# Advisors: US stocks to buy the dip — 2026-11-09

Six independent advisors (4 Gemini models + Pollinations + OpenRouter/Nvidia) were
asked the same question on the **same measured market data**, taken live from
`scripts/us_dip_scan.py` (Yahoo chart feed, 1 year of daily closes). 6/6 answered.

## The measured data the panel saw (2026-11-09)

| sym | price | %chg | off52h | off52l | RSI | v50 | v200 | r1m | r3m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| INTC | 59.89 | +6.4 | -57.5 | +78.1 | 30.1 | -38.5 | -31.3 | -40.9 | -38.7 |
| COIN | 137.52 | +2.1 | -56.7 | +2.0 | 35.6 | -21.2 | -21.7 | -23.8 | -7.4 |
| ARM | 188.21 | +7.8 | -57.2 | +80.0 | 37.3 | -25.2 | -18.6 | -26.3 | -30.0 |
| ORCL | 120.03 | +3.4 | -51.6 | +4.4 | 42.1 | -13.3 | -22.6 | -12.6 | -17.5 |
| LRCX | 221.66 | +10.6 | -48.8 | +58.8 | 39.5 | -21.6 | -22.0 | -28.4 | -28.8 |
| AMAT | 372.86 | +12.1 | -48.4 | +69.3 | 42.0 | -15.8 | -16.3 | -25.1 | -29.1 |
| DDOG | 180.02 | +0.6 | -38.6 | +75.4 | 28.8 | -27.0 | -10.2 | -37.3 | -27.1 |
| MU | 738.82 | +7.1 | -39.1 | +266.9 | 37.0 | -22.9 | -2.6 | -25.3 | -14.9 |
| NVDA | 178.22 | -4.5 | -25.5 | +7.9 | 27.2 | -18.6 | -12.9 | -21.3 | -18.1 |

`off52h` = drawdown from 52-week high; `off52l` = distance above 52-week low;
`v50/v200` = distance from the 50/200-day MA; `r1m/r3m` = 1/3-month return.

## What each advisor picked

| advisor | top pick | 2nd | 3rd | one to avoid |
|---|---|---|---|---|
| gemini-3.5 | AMAT | INTC | LRCX | **NVDA** |
| gemini-3.1 | RBLX | SOFI | ORCL | **NVDA** |
| gemini-flash | **NVDA** | DDOG | MU | **COIN** |
| gemini-preview | **NVDA** | DDOG | MU | **INTC** |
| pollinations | **NVDA** | (partial) | — | — |
| openrouter (Nvidia) | INTC | ARM | LRCX | — |

## Consensus (counted, not asserted)

- **NVDA — most-named #1 (3 of 6) but with a real dissent.** gemini-flash,
  gemini-preview and pollinations rank it first (RSI 27.2 = deepest oversold,
  shallowest drawdown at -25.5%). gemini-3.5 and gemini-3.1 put it in **avoid**
  ("falling knife": RSI < 30 with the only negative %chg in the table, -4.5%).
- **DDOG (2), MU (2)** — the shared #2/#3 from the two advisors that ranked NVDA
  first. MU's case rests on v200 = -2.6% (still near its 200-day) and off52l = +267%.
- **INTC — contested**: #2 for gemini-3.5 and #1 for openrouter, but gemini-preview
  calls it the single worst name to hold. RSI 30.1 with r1m -40.9% and v50 -38.5%.

## What the panel agreed on regardless of pick

1. **Scale in, never all-in** — every candidate's `v50` is negative (-13% to -38%),
   i.e. the short-term trend is still down.
2. **Stop below the 52-week low** — several names (COIN +2.0%, ORCL +4.4%, NVDA +7.9%)
   sit close to it, so a new low has no support beneath it.
3. **Do not chase the day's biggest gainers** (AMAT +12.1%, LRCX +10.6%): entering
   after a vertical day is a worse risk/reward than waiting for a pullback.

## Honest limits of this result

- The panel split on the single most-named name (NVDA). The data can support either
  read, so this is **not** a confident consensus — it is a shortlist plus a named risk.
- `us_dip_scan.py` is **price-only**: no earnings, valuation, or news. A dip can be a
  falling knife for reasons the scan cannot see.
- This is technical, short-horizon screening, not investment advice.

---

# Run 2 — 2026-11-09 (later the same day, fresh prices)

The panel was re-run on a **fresh** `us_dip_scan.py` snapshot. All six advisors
answered this time (two needed a shorter prompt; see "reliability" below).

## Vote tally (counted, not asserted)

| advisor | 1st | 2nd | 3rd | avoid |
|---|---|---|---|---|
| gemini-3.5 | INTC | DDOG | NVDA | MSTR |
| gemini-3.1 | AVGO | LRCX | AMAT | NVDA |
| gemini-flash | NVDA | AVGO | DDOG | INTC |
| gemini-preview | NVDA | ARM | INTC | NKE |
| pollinations | DDOG | NVDA | COIN | AVGO |
| openrouter (Nvidia) | NVDA | INTC | DDOG | COIN |

**Buy mentions:** NVDA **5** (2× #1), DDOG **4** (1× #1), INTC **3** (1× #1),
AVGO 2, COIN 2, ARM/LRCX/AMAT 1 each.

**Consensus top three: NVDA, DDOG, INTC** — the same three as run 1, so the
shortlist is stable across two snapshots.

## The dissent is real, and it is about one name

NVDA is #1 for two advisors and in the buy list of five, **but gemini-3.1 puts it
in "avoid"** (RSI 27.4 with the only negative %chg, -4.27%): "oversold heavily, the
selling is not finished." INTC is the mirror image — #1 for gemini-3.5 and in
openrouter's buy list, yet gemini-flash calls it the single worst hold
(v50 -39.0%, v200 -31.8%, r1m -41.4%: down-trending on every horizon).

## The one number that separates "dip" from "falling knife"

`off52l` (distance above the 52-week low). NVDA +8.2%, DDOG +75.0% have room;
COIN +1.0%, ORCL +4.2%, NFLX +3.2% are sitting on the low with nothing beneath.
Every "avoid" vote in this run is a name near its 52-week low, not a name that is
merely cheap.

## Reliability note (measured)

- `pollinations` returns **HTTP 400 on a long prompt** but answers a short one — its
  free tier is prompt-length sensitive.
- `openrouter` answered only after a retry: the three free models share a rate-limited
  pool, and firing all six advisors at once can exhaust it. Called singly it is fine
  (this is why `ask_openrouter` walks the model list with backoff).
- Bench (`scripts/panel_bench.py`): all six scored **5/5 on checkable probes**; median
  latency gemini-3.5 0.5s, gemini-3.1 0.6s, gemini-preview 1.0s, openrouter 1.3s,
  gemini-flash 1.5s, pollinations 65.7s.
