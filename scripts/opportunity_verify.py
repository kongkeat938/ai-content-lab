#!/usr/bin/env python3
"""Re-open every stored request and decide what it actually is.

Discovery found postings. A posting is not a customer, and an old URL is not an
opportunity. This pass looks at each one again, live, and answers three
questions with evidence:

  * is the page still there            -> verified / unverified / expired
  * does it still ask for our work      -> the title must appear on the page
  * can we even reply without an account -> channel feasibility, measured

Ranking only ever considers `verified` rows, and a row carries the numbers it
was ranked on so the order can be argued with. Nothing here sends anything.

    python3 scripts/opportunity_verify.py                 # verify + rank
    python3 scripts/opportunity_verify.py --report        # counts only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proposal_draft import fits_service, sample_kind  # one definition of "work we can deliver"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROSPECTS = os.environ.get("PROSPECT_STORE") or os.path.join(ROOT, "content", "prospects_external.json")
OUT = os.environ.get("OPPORTUNITY_STORE") or os.path.join(ROOT, "content", "opportunities.json")
UA = "Mozilla/5.0 (compatible; ak-prospect-research/1.0; +https://github.com/kongkeat938/ai-content-lab)"
USD_THB = 35.0
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")

# How a reply would have to travel. Measured from the platform's own pages.
CHANNELS = {
    "freelancer.com": ("bidding_requires_login", False,
                       "the bid button is behind a free account; K has not approved one"),
    "craigslist.org": ("relay_email_then_captcha", False,
                       "reply relay is public but the form needs a captcha and a mailbox we may use"),
    "freelancermap.com": ("contact_form_after_login", False,
                          "contact form is gated by a free account"),
    "news.ycombinator.com": ("public_post_or_email", True,
                             "a public comment or the address printed in the post"),
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fetch(url: str, timeout: int = 30) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,th;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:  # noqa: BLE001 - a dead host is a measurement, not a crash
        return 0, ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9ก-๙ ]+", " ", (s or "").lower()).strip()


def title_on_page(title: str, page: str) -> bool:
    """The ad must still show its own headline. Comparing 25 normalised
    characters is enough to tell a live ad from a 200-status soft-404."""
    key = _norm(title)[:25]
    return bool(key) and key in _norm(page)


# A project page shows a RANGE and a currency ("$30-250 AUD"). Reading the first
# dollar figure as USD produced 2,135 THB where the real floor was $30 AUD, so
# every budget is now kept as text plus a conservative low/high in THB.
FX_TO_THB = {"USD": 35.0, "AUD": 23.0, "CAD": 25.0, "EUR": 38.0, "GBP": 44.0,
             "NZD": 21.0, "SGD": 26.0, "HKD": 4.5, "THB": 1.0, "INR": 0.42,
             "MYR": 8.0, "PHP": 0.6, "IDR": 0.0022, "VND": 0.0014, "JPY": 0.23,
             "CNY": 4.9, "KRW": 0.026, "AED": 9.5, "SAR": 9.3, "ZAR": 1.9,
             "BRL": 6.4, "MXN": 1.9, "TRY": 1.0, "RUB": 0.36, "PKR": 0.13,
             "BDT": 0.29, "NGN": 0.022, "KES": 0.23, "EGP": 0.7, "PLN": 8.6,
             "SEK": 3.3, "NOK": 3.2, "DKK": 5.1, "CHF": 39.0, "ILS": 9.4}
CUR = "USD|AUD|CAD|EUR|GBP|NZD|SGD|HKD|THB|INR|MYR|PHP|IDR|VND|JPY|CNY|KRW|AED|SAR|ZAR|BRL|MXN|TRY|RUB|PKR|BDT|NGN|KES|EGP|PLN|SEK|NOK|DKK|CHF|ILS"
RANGE_RE = re.compile(
    rf"([$฿€£₹₩₽])\s?([\d,]+(?:\.\d+)?)\s?(?:-|–|to)\s?([$฿€£₹₩₽])?\s?([\d,]+(?:\.\d+)?)"
    rf"\s?({CUR})?", re.I)
SINGLE_RE = re.compile(rf"([$฿€£₹₩₽])\s?([\d,]+(?:\.\d+)?)\s?({CUR})?", re.I)
SYM = {"$": "USD", "฿": "THB", "€": "EUR", "£": "GBP", "₹": "INR", "₩": "KRW", "₽": "RUB"}


def _to_thb(value: float, cur: str) -> float:
    return value * FX_TO_THB.get(cur.upper(), FX_TO_THB["USD"])


META_RE = re.compile(r'<meta[^>]+(?:name="description"|property="og:description")[^>]+content="([^"]{20,600})"', re.I)


def budget(page: str, fallback_text: str) -> dict:
    """Return {raw, low_thb, high_thb, currency, basis}.

    The only trustworthy figure is the one in the buyer's own words, which the
    page repeats in its description meta tag. A "$30-250 CAD" three quarters of
    the way down the page belonged to a *similar projects* widget, so the rest of
    the HTML is never scanned for money; the listing card is the last resort and
    is labelled as such.
    """
    meta = META_RE.search(page or "")
    head = (page or "")[:120000]   # the meta tag lives here; the rest is widgets
    for src, basis in (((meta.group(1) if meta else ""), "buyer's description"),
                       (head, "page head"),
                       (fallback_text, "listing card (platform-converted)")):
        if not src:
            continue
        m = RANGE_RE.search(src)
        if m:
            cur = (m.group(5) or SYM.get(m.group(1), "USD")).upper()
            lo, hi = float(m.group(2).replace(",", "")), float(m.group(4).replace(",", ""))
            return {"raw": m.group(0).strip(), "currency": cur,
                    "low_thb": round(_to_thb(min(lo, hi), cur)),
                    "high_thb": round(_to_thb(max(lo, hi), cur)), "basis": basis}
        m = SINGLE_RE.search(src)
        if m:
            cur = (m.group(3) or SYM.get(m.group(1), "USD")).upper()
            val = float(m.group(2).replace(",", ""))
            return {"raw": m.group(0).strip(), "currency": cur,
                    "low_thb": round(_to_thb(val, cur)), "high_thb": None, "basis": basis}
    return {"raw": "", "currency": "", "low_thb": None, "high_thb": None, "basis": "none"}


def deadline_days(page: str, fallback: str) -> int | None:
    for src in (page[:200000], fallback):
        m = re.search(r"(\d+)\s+days?\s+left", src, re.I)
        if m:
            return int(m.group(1))
    return None


def channel_for(item: dict, page: str) -> dict:
    url = item.get("url") or ""
    host = re.sub(r"^www\.", "", url.split("/")[2]) if "//" in url else ""
    if host not in CHANNELS and item.get("source") in CHANNELS:
        host = item["source"]
    kind, permitted, why = CHANNELS.get(host, ("unknown", False, "no measured contact path"))
    detail = why
    if host == "news.ycombinator.com":
        found = EMAIL.search(page or "")
        if not found:
            kind, permitted = "public_comment_requires_account", False
            detail = "no address in the post; replying on HN needs an approved account"
    return {"kind": kind, "permitted_now": permitted, "detail": detail}


def verify_item(item: dict) -> dict:
    status, page = fetch(item["url"])
    out = dict(item)
    out["checked_at"] = now()
    out["http_status"] = status
    on_page = title_on_page(item.get("title", ""), page)
    out["title_confirmed_on_page"] = on_page
    if status in (404, 410) or status == 0:
        out["state"] = "expired" if status in (404, 410) else "unreachable"
    elif status == 200 and on_page:
        out["state"] = "verified"
    else:
        out["state"] = "unverified"
    b = budget(page, item.get("budget_text", ""))
    d = deadline_days(page, item.get("deadline_text", ""))
    out["budget"] = b
    out["budget_thb"] = b["low_thb"]
    out["days_left"] = d
    out["channel"] = channel_for(item, page)
    out["sample_fit"] = sample_kind(item)
    return out


def score(row: dict) -> tuple[int, list[str]]:
    why, s = [], 0
    b = row.get("budget_thb")
    if b is None:
        why.append("no budget on the page (+0)")
    elif b >= 1500:
        s += 30; why.append(f"budget floor {b} THB covers pack C (+30)")
    elif b >= 750:
        s += 25; why.append(f"budget floor {b} THB covers pack B (+25)")
    elif b >= 490:
        s += 18; why.append(f"budget floor {b} THB covers pack A (+18)")
    else:
        s += 8; why.append(f"budget floor {b} THB = right-sized only (+8)")
    blob = f"{row.get('title','')} {row.get('text','')}".lower()
    if any(t in blob for t in ("9:16", "vertical", "reel", "short", "tiktok")):
        s += 20; why.append("asks for vertical short-form (+20)")
    if any(t in blob for t in ("per week", "weekly", "ongoing", "batch", "series")):
        s += 15; why.append("repeat work stated (+15)")
    if row.get("days_left") and row["days_left"] >= 3:
        s += 10; why.append(f"{row['days_left']} days left (+10)")
    if "verified" in (row.get("contact_public") or "").lower():
        s += 10; why.append("buyer's payment method verified (+10)")
    if row.get("channel", {}).get("permitted_now"):
        s += 15; why.append("contactable without a new account (+15)")
    return min(s, 100), why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="verify at most N rows (0 = all)")
    ap.add_argument("--rescore", action="store_true",
                    help="re-apply scope + score to the stored rows, no network")
    a = ap.parse_args()

    if a.report:
        db = load(OUT, {"rows": []})
        rows = db.get("rows", [])
        by = {}
        for r in rows:
            by[r["state"]] = by.get(r["state"], 0) + 1
        print(f"rows checked      : {len(rows)}")
        for k in ("verified", "unverified", "expired", "unreachable"):
            print(f"  {k:12} {by.get(k, 0)}")
        contactable = [r for r in rows if r.get("channel", {}).get("permitted_now")]
        print(f"contactable now   : {len(contactable)} (no new account)")
        print(f"ready to send     : 0  (sending needs K's separate approval)")
        return 0

    if a.rescore:
        db = load(OUT, {"rows": []})
        rows = db.get("rows", [])
        for r in rows:
            ok, why_not = fits_service(r)
            if r["state"] == "verified" and not ok:
                r["state"] = "out_of_scope"
                r["out_of_scope_reason"] = why_not
        ranked = []
        for r in rows:
            if r["state"] != "verified":
                continue
            sc, why = score(r)
            r["score"], r["why"] = sc, why
            ranked.append(r)
        ranked.sort(key=lambda r: (-r["score"], -(r.get("budget_thb") or 0), r["title"]))
        top = ranked[: a.top]
        for n, r in enumerate(top, 1):
            r["rank"] = n
        db.update({"checked_at": now(), "top": [r["id"] for r in top], "top_count": len(top),
                   "verified_count": len(ranked),
                   "contactable_count": sum(1 for r in rows if r.get("channel", {}).get("permitted_now"))})
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(db, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"rescored: verified {len(ranked)}, out_of_scope "
              f"{sum(1 for r in rows if r['state']=='out_of_scope')}, top {len(top)}")
        for r in rows:
            r.setdefault("sample_fit", sample_kind(r))
        for r in top:
            print(f"  {r['rank']:>2}. {r['score']:>3}/100 {r.get('budget_thb') or '-':>6} THB "
                  f"{r['title'][:42]} -> {r['sample_fit']}/{r['channel']['kind']}")
        return 0

    src = load(PROSPECTS, {"items": []})
    items = [i for i in src.get("items", []) if i.get("status") != "expired"]
    if a.limit:
        items = items[: a.limit]
    rows = []
    for i, item in enumerate(items, 1):
        r = verify_item(item)
        rows.append(r)
        print(f"  [{i}/{len(items)}] {r['state']:11} {r['http_status']:>3} "
              f"{r.get('budget_thb') or '-':>6} THB  {item['title'][:52]}")
    ranked = []
    for r in rows:
        if r["state"] != "verified":
            continue
        sc, why = score(r)
        r["score"], r["why"] = sc, why
        ranked.append(r)
    ranked.sort(key=lambda r: (-r["score"], -(r.get("budget_thb") or 0), r["title"]))
    top = ranked[: a.top]
    for n, r in enumerate(top, 1):
        r["rank"] = n
    db = {"checked_at": now(), "rows": rows, "top": [r["id"] for r in top],
          "top_count": len(top), "verified_count": len(ranked),
          "contactable_count": sum(1 for r in rows if r.get("channel", {}).get("permitted_now"))}
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, OUT)
    print(f"\nverified {len(ranked)}, expired {sum(1 for r in rows if r['state']=='expired')}, "
          f"unverified {sum(1 for r in rows if r['state']=='unverified')}, "
          f"unreachable {sum(1 for r in rows if r['state']=='unreachable')}")
    print(f"top {len(top)} written to {os.path.relpath(OUT, ROOT)}")
    if len(top) < a.top:
        print(f"NOTE: only {len(top)} verified opportunities — the list is not padded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
