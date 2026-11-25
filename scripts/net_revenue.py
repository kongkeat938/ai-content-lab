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
import sys

PACKAGES = (("A", 5, 490), ("B", 10, 890), ("C", 20, 1590))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commission", type=float, default=0.18)
    ap.add_argument("--vat", type=float, default=0.07)
    ap.add_argument("--withdrawal", type=float, default=0.01)
    ap.add_argument("--target", type=float, default=5200)
    a = ap.parse_args()
    cut = a.commission * (1 + a.vat) + a.withdrawal
    print(f"assumption: commission {a.commission:.0%} + VAT {a.vat:.0%} on the commission "
          f"+ {a.withdrawal:.0%} withdrawal = {cut:.2%} of the price")
    print(f"{'pack':4} {'clips':>5} {'price':>7} {'net':>8} {'orders to net ' + f'{a.target:.0f}':>22}")
    for name, clips, price in PACKAGES:
        net = price * (1 - cut)
        import math
        need = math.ceil(a.target / net)
        print(f"{name:4} {clips:>5} {price:>7} {net:>8.0f} {need:>22}")
    print("before income tax; the commission rate must be read from the seller page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
