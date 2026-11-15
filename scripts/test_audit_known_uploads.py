#!/usr/bin/env python3
"""The audit must count uploads made by a sibling rail on the same channels.

Measured 2026-11-15: kongkeat938/ax-workspace `.github/workflows/auto-shorts.yml`
(the predecessor of this repo) published Shorts to the same three channels with the
same `YT_CH*_REFRESH_TOKEN` secrets, but recorded them only in its own
`docs/published.json`. This repo's audit saw them as "in NO manifest" and warned K
they were an outside "rogue" uploader. They were ours. `content/known_uploads.json`
now carries them, and `recorded_entries` must count them.

This guard can FAIL: point `recorded_entries` at a channel whose known uploads exist
and it must return them; drop the `uploads` handling and it goes blind again.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_channels as ac  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KNOWN = ROOT / "content" / "known_uploads.json"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    if not KNOWN.exists():
        fail("content/known_uploads.json is missing; the sibling rail's uploads are "
             "not recorded and the audit will call them rogue again")
    doc = json.loads(KNOWN.read_text(encoding="utf-8"))
    ups = doc.get("uploads") or []
    if not ups:
        fail("content/known_uploads.json has no uploads")
    sample = ups[0]
    cid = sample["channel_id"]
    if sample["video_id"] not in ac.recorded_ids(cid):
        fail(f"{sample['video_id']} is in known_uploads.json for {cid} but "
             f"recorded_entries does not count it -- the audit is blind to the "
             f"sibling rail again")

    # And the guard can FAIL: a bogus channel must not inherit another channel's ids.
    if sample["video_id"] in ac.recorded_ids("UCdoes-not-exist-0000000000"):
        fail("recorded_entries leaks one channel's known uploads into another")

    # Every known upload must name a channel we actually run, so a typo cannot hide
    # a video on a channel nobody audits.
    valid = {"UCI6EfsgM1HNjrYarvigxyrQ", "UCM3QO5L_pmj34n1JVlbhh-w", "UC7gCIu4G_7QCEJ8hJ-34zoQ"}
    bad = sorted({u["channel_id"] for u in ups} - valid)
    if bad:
        fail(f"known_uploads.json names unknown channels: {bad}")

    print(f"OK: the audit counts {len(ups)} sibling-rail uploads across "
          f"{len({u['channel_id'] for u in ups})} channels; they are no longer 'rogue'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
