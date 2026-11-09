#!/usr/bin/env python3
"""A git merge driver that unions the JSON records the upload rails append to.

The rails write append-only records -- the upload ledger, the remake manifests,
and the art/bed ledgers -- and several channel jobs can push at once. Measured
2026-11-09: publish-shorts (dharma) and remake (dharma) pushed in the same second,
a rebase left conflict markers in content/upload_log.json, and dharma's remake id
(QLUp6sV16fs, already live on YouTube) was never recorded, so the next run would
re-upload it.

Both sides of a conflict are real uploads, so the correct merge keeps both. This
driver recurses: objects are merged by key, arrays are unioned (order kept, no
duplicates), and a scalar clash keeps "ours". It is wired in through
.gitattributes (`merge=unionjson`) and configured by the workflows.

    git config merge.unionjson.driver "python3 scripts/git_union_merge.py %O %A %B"
"""
from __future__ import annotations

import json
import sys


def union(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = union(out[k], v) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        out, seen = [], set()
        for item in a + b:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out
    return a


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: git_union_merge.py <base> <ours> <theirs>", file=sys.stderr)
        return 2
    _, base_p, ours_p, theirs_p = sys.argv
    try:
        ours = json.load(open(ours_p, encoding="utf-8"))
    except (OSError, ValueError):
        return 1                       # not our file / unreadable: let git decide
    try:
        theirs = json.load(open(theirs_p, encoding="utf-8"))
    except (OSError, ValueError):
        theirs = {}
    try:
        base = json.load(open(base_p, encoding="utf-8"))
    except (OSError, ValueError):
        base = {}
    # Only union the keys the other side changed relative to the base, so an
    # entry one side deleted is not resurrected by a stale copy on the other.
    if isinstance(base, dict) and isinstance(ours, dict) and isinstance(theirs, dict):
        changed = {k: v for k, v in theirs.items() if base.get(k) != v}
        merged = union(ours, changed)
    else:
        merged = union(ours, theirs)
    with open(ours_p, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
