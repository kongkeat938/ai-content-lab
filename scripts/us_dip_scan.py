#!/usr/bin/env python3
"""Scan a US universe for names that have pulled back, with real market data.

Yahoo's public chart endpoint is the only free feed that answered (measured
2026-11-09); stockanalysis and most screeners sit behind Cloudflare. For each
symbol this pulls a year of daily closes and computes the numbers a "buy the
dip" question actually needs: drawdown from the 52-week high, RSI(14), and the
distance from the 50/200-day moving averages. It prints a ranked table; it does
not decide. The decision goes to the advisor panel (scripts/advise.py).

    python3 scripts/us_dip_scan.py
    python3 scripts/us_dip_scan.py --symbols AAPL,NVDA,AMD
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"

# A broad, liquid US universe: mega/large-cap tech, semiconductors, financials,
# healthcare, energy, consumer, and the sector indices that set the tone.
UNIVERSE = [
    # indices / macro
    "SPY", "QQQ", "IWM", "DIA", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "TLT", "GLD", "ARKK",
    # mega-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AVGO", "TSLA", "NFLX", "ORCL",
    # semis / hardware
    "AMD", "TSM", "MU", "INTC", "QCOM", "ARM", "SMCI", "ASML", "LRCX", "AMAT",
    # software / internet
    "CRM", "ADBE", "PLTR", "SNOW", "CRWD", "NET", "DDOG", "MDB", "SHOP", "UBER",
    "ABNB", "SNAP", "PINS", "RBLX", "COIN", "PYPL", "SQ", "SOFI", "MSTR",
    # financials
    "JPM", "BAC", "GS", "MS", "V", "MA", "BRK-B",
    # healthcare / consumer / industrial / energy
    "UNH", "LLY", "JNJ", "PFE", "MRK", "XOM", "CVX", "KO", "PEP", "WMT", "COST",
    "HD", "DIS", "NKE", "BA", "CAT", "DE", "F", "GM",
]


def fetch(symbol: str, timeout: int = 20) -> dict | None:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range=1y&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            d = json.load(fh)
        r = d["chart"]["result"][0]
        closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
        meta = r["meta"]
        return {"symbol": symbol, "closes": closes,
                "price": meta.get("regularMarketPrice"),
                "chg": meta.get("regularMarketChangePercent")}
    except Exception:  # noqa: BLE001 - a missing symbol must not stop the scan
        return None


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - 100 / (1 + rs)


def sma(closes: list[float], n: int) -> float | None:
    return sum(closes[-n:]) / n if len(closes) >= n else None


def metrics(row: dict) -> dict:
    c = row["closes"]
    price = row["price"] or c[-1]
    hi = max(c)
    lo = min(c)
    m = {
        "symbol": row["symbol"], "price": round(price, 2),
        "chg": round(row.get("chg") or 0, 2),
        "off_high": round((price - hi) / hi * 100, 1),
        "off_low": round((price - lo) / lo * 100, 1),
        "rsi": round(rsi(c) or 50, 1),
    }
    for n in (50, 200):
        s = sma(c, n)
        m[f"vs{n}"] = round((price - s) / s * 100, 1) if s else None
    if len(c) >= 21:
        m["ret1m"] = round((price - c[-21]) / c[-21] * 100, 1)
    if len(c) >= 64:
        m["ret3m"] = round((price - c[-64]) / c[-64] * 100, 1)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="comma list, else the built-in universe")
    ap.add_argument("--json", default=None, help="write the metrics to this path")
    a = ap.parse_args()
    symbols = a.symbols.split(",") if a.symbols else UNIVERSE
    with ThreadPoolExecutor(max_workers=12) as ex:
        rows = [r for r in ex.map(fetch, symbols) if r]
    ms = [metrics(r) for r in rows]
    # Rank by how far off the high, with oversold RSI weighted in; long-term
    # trend (vs200) is kept in the table so a broken chart is visible.
    ms.sort(key=lambda m: (m["off_high"] + (m["rsi"] - 50) * 0.6))
    hdr = f"{'sym':6}{'price':>9}{'%chg':>7}{'off52h':>8}{'off52l':>8}{'rsi':>6}{'v50':>7}{'v200':>7}{'r1m':>7}{'r3m':>7}"
    print(hdr)
    print("-" * len(hdr))
    for m in ms:
        print(f"{m['symbol']:6}{m['price']:>9}{m['chg']:>7}{m['off_high']:>8}"
              f"{m['off_low']:>8}{m['rsi']:>6}{m.get('vs50', 0):>7}{m.get('vs200', 0):>7}"
              f"{m.get('ret1m', 0):>7}{m.get('ret3m', 0):>7}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(ms, fh, ensure_ascii=False, indent=2)
        print(f"\nwrote {a.json} ({len(ms)} symbols)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
