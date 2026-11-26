#!/usr/bin/env python3
"""What actually lands in the bank after a marketplace takes its cut.

The first offer quoted a flat "10-20%" platform fee, which is a guess. Fastwork
charges a commission that depends on sales history, adds 7% VAT on that
commission, and 1% on a withdrawal. This turns those into one formula so the
price list can be checked instead of believed.

    python3 scripts/net_revenue.py --commission 0.18 --target 5200

The defaults are ASSUMPTIONS until the seller page is read: print them as
assumptions, never as fact.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def packages() -> list[tuple[str, int, int]]:
    with open(os.path.join(ROOT, "content", "packages.json"), encoding="utf-8") as fh:
        return [(p["id"], p["clips"], p["price"]) for p in json.load(fh)["packages"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commission", type=float, default=0.18)
    ap.add_argument("--vat", type=float, default=0.07)
    ap.add_argument("--withdrawal", type=float, default=0.01)
    ap.add_argument("--target", type=float, default=5200)
    ap.add_argument("--minutes-per-clip", type=float, default=12.0,
                    help="ASSUMPTION until the first order is timed: cut+QA minutes per clip")
    ap.add_argument("--thb-per-day", type=float, default=0.0,
                    help="optional daily cash cost (rent of tools etc.); 0 = none")
    a = ap.parse_args()
    cut = a.commission * (1 + a.vat) + a.withdrawal
    print(f"assumption: commission {a.commission:.0%} + VAT {a.vat:.0%} on the commission "
          f"+ {a.withdrawal:.0%} withdrawal = {cut:.2%} of the price")
    print(f"{'pack':4} {'clips':>5} {'price':>7} {'net':>8} {'orders to net ' + f'{a.target:.0f}':>22}")
    for name, clips, price in packages():
        net = price * (1 - cut)
        import math
        need = math.ceil(a.target / net)
        print(f"{name:4} {clips:>5} {price:>7} {net:>8.0f} {need:>22}")
    print("before income tax; the commission rate must be read from the seller page")

    # Cash and time are two different costs and K asked to see them apart: a
    # "0 THB" order still spends the owner's hours, which is the resource the
    # whole project exists to protect.
    print("\ntime cost (assumption: "
          f"{a.minutes_per_clip:.0f} min of human time per clip, until an order is timed)")
    print(f"{'pack':4} {'hours':>6} {'net THB':>8} {'THB/hour':>9} {'net - cash/day':>15}")
    for name, clips, price in packages():
        net = price * (1 - cut)
        hours = clips * a.minutes_per_clip / 60
        per_hour = net / hours if hours else 0
        print(f"{name:4} {hours:>6.1f} {net:>8.0f} {per_hour:>9.0f} {net - a.thb_per_day:>15.0f}")
    print("direct cash cost per order: 0 THB (free tiers, own hardware) -- hours are NOT free")
    return 0


if __name__ == "__main__":
    sys.exit(main())
