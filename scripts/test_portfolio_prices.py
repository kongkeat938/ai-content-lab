#!/usr/bin/env python3
"""One price, everywhere.

content/packages.json is the source. This fails when the offer doc, the public
page or a draft drifts from it, and when the page claims something we cannot
show (a client review, a delivered job).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def main() -> int:
    packs = json.load(open(os.path.join(ROOT, "content", "packages.json"), encoding="utf-8"))
    doc = open(os.path.join(ROOT, "docs", "OFFER-2026-11-25.md"), encoding="utf-8").read()

    print("prices agree")
    for p in packs["packages"]:
        check(f"pack {p['id']} ({p['price']}) is in the offer doc", f"{p['price']:,}" in doc
              or f"{p['price']} " in doc, str(p["price"]))
    stale = [n for n in ("890", "710") if n in doc]
    check("no stale price survives in the doc", not stale, str(stale))

    print("page is generated, not hand-edited")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build_portfolio.py"), "--check"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    check("the page matches packages.json", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])

    page_path = os.path.join(ROOT, "docs", "portfolio", "index.html")
    page = open(page_path, encoding="utf-8").read()
    print("page claims only what we can show")
    for p in packs["packages"]:
        check(f"pack {p['id']} price is on the page", f"{p['price']:,}" in page, str(p["price"]))
    check("the page says the samples are self-produced", packs["samples_note"][:20] in page)
    banned = ("รีวิวจากลูกค้า", "ลูกค้าพึงพอใจ", "testimonial", "★★★★★", "ผลลัพธ์การขายเพิ่ม")
    hits = [b for b in banned if b in page]
    check("no unsupported social proof", not hits, str(hits))
    for m in re.findall(r'<source src="media/([^"]+)"', page):
        check(f"{m} exists", os.path.exists(os.path.join(ROOT, "docs", "portfolio", "media", m)))

    listing_path = os.path.join(ROOT, "docs", "FASTWORK-LISTING-2026-11-27.md")
    print("the listing sheet carries the same price and the same limits")
    listing = open(listing_path, encoding="utf-8").read()
    for p in packs["packages"]:
        check(f"pack {p['id']} price is on the listing", f"{p['price']:,}" in listing, str(p["price"]))
    stale = [n for n in ("890", "710") if n in listing]
    check("no stale price on the listing", not stale, str(stale))
    # Only the paste-ready block (lines quoted with "> ") goes on the site, so that
    # is what must not promise reach; the sheet also *names* these phrases as
    # forbidden, and a whole-file grep would flag its own rule.
    paste = "\n".join(l for l in listing.splitlines() if l.startswith("> "))
    check("the paste-ready block exists", len(paste) > 300, str(len(paste)))
    hits = [b for b in banned + ("รับประกันยอดวิว", "มาตรฐานแพลตฟอร์ม") if b in paste]
    check("the paste-ready copy promises no reach and no platform standard", not hits, str(hits))
    check("the listing tells K the account is his step",
          "ak never signs up as K" in listing)

    print("\nPASS test_portfolio_prices" if not FAILED else f"\nFAIL test_portfolio_prices: {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
