#!/usr/bin/env python3
"""Read the PC1 art library, or keep a local copy of its index fresh.

The status page cannot read D:\art_library directly, and asking PC1 for the whole
index on every page load would hammer the link. This polls on a timer and writes
the list, so the counter K looks at is a measurement of the real folder.

    python3 scripts/art_library.py index --url https://host/art --out site/art_index.json
    python3 scripts/art_library.py index --url https://host/art --out site/art_index.json --watch 60
    python3 scripts/art_library.py claim --url https://host/art --id 01 --out art.jpg
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

DEFAULT_URL = os.environ.get("ART_LIBRARY_URL", "")


def fetch(url: str) -> list[str]:
    with urllib.request.urlopen(url.rstrip("/") + "/index.json", timeout=60) as fh:
        raw = fh.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"index.json is not JSON: {exc}") from exc
    return sorted(str(i.get("file", "")) for i in data.get("items", [])
                  if str(i.get("file", "")).lower().endswith(".png"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["index", "claim"])
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--out", required=True)
    ap.add_argument("--id", help="clip id, for `claim`")
    ap.add_argument("--ledger", help="art ledger, for `claim`")
    ap.add_argument("--watch", type=float, default=0,
                    help="refresh every N seconds instead of once")
    args = ap.parse_args()
    if not args.url:
        raise SystemExit("--url is required (or set ART_LIBRARY_URL)")

    if args.action == "claim":
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, here)
        import make_short as MS
        d = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(d, exist_ok=True)
        got = MS.library_art(d, args.id or os.path.basename(d), args.url, args.ledger)
        if not got:
            print("no unused piece available", file=sys.stderr)
            return 1
        if os.path.abspath(got) != os.path.abspath(args.out):
            os.replace(got, args.out)
        print(args.out)
        return 0

    # One-shot mode is a GATE: if the library could not be read it must exit
    # non-zero, never 0. Measured 2026-11-19 (Gemini review): a failed fetch was
    # printed and then fell through to `return 0`, so a caller checking the exit
    # code read a dead library as a clean refresh. Watch mode keeps the last good
    # index on purpose, so there a failure is reported but not fatal.
    failed = False
    while True:
        try:
            files = fetch(args.url)
        except Exception as exc:  # noqa: BLE001 - keep the last good index
            failed = True
            print(f"index fetch failed: {exc}", flush=True)
        else:
            failed = False
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            tmp = f"{args.out}.{os.getpid()}.part"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(files, fh)
            os.replace(tmp, args.out)
            print(f"{len(files)} pieces", flush=True)
        if args.watch <= 0:
            return 1 if failed else 0
        time.sleep(args.watch)


if __name__ == "__main__":
    sys.exit(main())
