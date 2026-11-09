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
