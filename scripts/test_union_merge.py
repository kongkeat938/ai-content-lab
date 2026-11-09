#!/usr/bin/env python3
"""Guard the append-only ledgers against a lost record on a racing push.

Measured 2026-11-09: publish-shorts (dharma) and remake (dharma) pushed in the
same second, the rebase left conflict markers in content/upload_log.json, and
dharma's remake id (QLUp6sV16fs, already live on YouTube) was never recorded --
the next run would have re-uploaded it. Two fixes are checked here: the union
merge driver keeps both sides, and the rails share one concurrency group per
channel so the race cannot start.

    python3 scripts/test_union_merge.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run_driver(base, ours, theirs):
    d = tempfile.mkdtemp()
    paths = {}
    for name, obj in (("base", base), ("ours", ours), ("theirs", theirs)):
        p = os.path.join(d, f"{name}.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        paths[name] = p
    r = subprocess.run([sys.executable, os.path.join(HERE, "git_union_merge.py"),
                        paths["base"], paths["ours"], paths["theirs"]],
                       capture_output=True, text=True)
    with open(paths["ours"], encoding="utf-8") as fh:
        return r.returncode, json.load(fh)


def main() -> int:
    fails = []

    # 1. the driver unions both sides of an upload ledger.
    rc, merged = run_driver(
        {"channels": {"dharma": ["t1", "t2"]}},
        {"channels": {"dharma": ["t1", "t2", "t3"]}},
        {"channels": {"dharma": ["t1", "t2", "t4"]}})
    if rc != 0:
        fails.append(f"merge driver exited {rc}")
    elif merged["channels"]["dharma"] != ["t1", "t2", "t3", "t4"]:
        fails.append(f"upload ledger not unioned: {merged}")

    # 2. the driver unions two channels' remake records.
    rc, merged = run_driver(
        {"shorts": {}},
        {"shorts": {"35": {"video_id": "NEW"}}},
        {"shorts": {"36": {"video_id": "OTHER"}}})
    if set(merged["shorts"]) != {"35", "36"}:
        fails.append(f"remake records not merged: {merged}")

    # 3. .gitattributes wires the driver to every append-only ledger.
    ga = open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read()
    for pat in ("content/upload_log.json", "content/*_shorts_remakes.json",
                "content/art_ledger_*.json", "content/bed_ledger_*.json"):
        if f"{pat} " not in ga or "merge=unionjson" not in ga:
            fails.append(f".gitattributes missing unionjson for {pat}")

    # 4. publish and remake share one concurrency group per channel, so the race
    #    that lost the id cannot start.
    pub = open(os.path.join(ROOT, ".github/workflows/publish-shorts.yml"),
               encoding="utf-8").read()
    rem = open(os.path.join(ROOT, ".github/workflows/remake-shorts.yml"),
               encoding="utf-8").read()
    if "group: shorts-upload-${{ matrix.channel }}" not in pub:
        fails.append("publish-shorts: concurrency group not shared per channel")
    if "group: shorts-upload-${{ matrix.slug }}" not in rem:
        fails.append("remake-shorts: concurrency group not shared per channel")

    if fails:
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: append-only ledgers union-merge and the upload rails are serialised")
    return 0


if __name__ == "__main__":
    sys.exit(main())
