#!/usr/bin/env python3
"""Guard: pc1_fix_remote.ps1 must open the PUBLIC funnel, not only tailnet serve.

Measured 2026-11-15: the pod (a GitHub Actions runner / cloud agent) is NOT a
member of the PC1 tailnet, so `tailscale serve` alone leaves
`desktop-rgk6jkb.tail8740ad.ts.net` NXDOMAIN from the pod -- the whole bridge looks
dead even though PC1 is up and healthy. The pod reaches PC1 only through the public
funnel. The script shipped with `serve` only, so re-running it left the pod blind.
This test fails if the funnel step is ever dropped again.

    python3 scripts/test_pc1_funnel.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "ops", "pc1_fix_remote.ps1")


def main() -> int:
    src = open(SCRIPT, encoding="utf-8").read()
    if "& $ts serve --bg $Port" not in src:
        print("FAIL: the tailnet serve step is gone")
        return 1
    if "& $ts funnel --bg $Port" not in src:
        print("FAIL: the script never enables the public funnel; a pod outside the "
              "tailnet would see NXDOMAIN and the bridge would look dead")
        return 1
    # The funnel result must be reported so K/ak can see it worked.
    if not re.search(r"FUNNEL_URL=", src):
        print("FAIL: the funnel URL is not reported")
        return 1
    print("ok  tailnet serve is set up")
    print("ok  the public funnel is enabled (pod can reach PC1 off-tailnet)")
    print("ok  FUNNEL_URL is reported")
    print("\nOK: pc1_fix_remote.ps1 keeps the bridge reachable from a pod")
    return 0


if __name__ == "__main__":
    sys.exit(main())
