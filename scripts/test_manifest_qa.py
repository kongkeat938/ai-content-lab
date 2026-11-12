#!/usr/bin/env python3
"""Guard the manifest QA gate: an empty receipt must not veto a verified video.

Measured 2026-11-09: the night build passed its gates, but its manifest push lost
a race, so a recovery run skipped the build -- and had no receipt. add_release_to_
manifest graded that empty receipt as D (verdict is None) and wrote state=blocked,
so publish_batch skipped a video that had actually passed. Two rules must hold:

  * no receipt -> leave the state alone (never invent a veto)
  * a passing (re)grade -> clear an earlier veto (ready), or a fixed build is
    blocked forever

    python3 scripts/test_manifest_qa.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import add_release_to_manifest as A  # noqa: E402
import qa_gate  # noqa: E402

FAILS = []


def check(name: str, ok: bool, got: str = "") -> None:
    print(("  ok   " if ok else "  FAIL ") + name + (f" -- {got}" if got else ""))
    if not ok:
        FAILS.append(name)


def receipt(hook_sec: float) -> dict:
    return {
        "verdict": "pass",
        "audio_info": {"hook": {"duration_sec": hook_sec}, "duration_sec": 7228},
        "video_info": {"duration_sec": 7228, "chapters": 27,
                       "chapter_seconds": [250.0] * 27, "true_peak_dbfs": -3.1},
    }


def main() -> int:
    # 1. No receipt (build skipped) -> state is left untouched, NOT blocked.
    e = {"state": "ready"}
    A.apply_qa_gate(e, {})
    check("an empty receipt does not veto", e["state"] == "ready", e["state"])

    # 2. A good receipt -> ready.
    e = {"state": "ready"}
    A.apply_qa_gate(e, receipt(12.0))
    check("a passing build stays ready", e["state"] == "ready", e["state"])

    # 3. A 40 s hook (the real 2026-11-09 failure) -> blocked.
    e = {"state": "ready"}
    A.apply_qa_gate(e, receipt(40.3))
    check("an over-long hook is vetoed", e["state"] == "blocked", e["state"])

    # 4. A passing re-grade clears an earlier veto.
    e = {"state": "blocked"}
    A.apply_qa_gate(e, receipt(12.0))
    check("a passing re-grade clears a prior veto", e["state"] == "ready", e["state"])

    # 5. An already-published video is never un-published by the gate.
    e = {"state": "published", "video_id": "abc"}
    A.apply_qa_gate(e, receipt(40.3))
    check("a published entry keeps its state", e["state"] == "published", e["state"])

    # 5b. A *passing* re-grade of an already-live key must not reset it to ready
    #     either -- that is the 2026-11-12 defect: a rebuilt published key
    #     (night_auto_202646) was flipped published -> ready beside its live
    #     video_id, which is one --forget away from a duplicate upload.
    e = {"state": "published", "video_id": "abc"}
    A.apply_qa_gate(e, receipt(12.0))
    check("a live video is not reset to ready by a re-grade",
          e["state"] == "published", e["state"])
    vids = [{"key": "k", "state": "published", "video_id": "abc"}]
    entry = {"key": "k", "state": "ready", "duration_sec": 7208.3}
    A.apply_qa_gate(entry, receipt(12.0))
    A.queue_entry(vids, entry, receipt(12.0))
    check("the manifest merge keeps a live video published",
          vids[0]["state"] == "published", vids[0]["state"])

    # 6. The ordering bug: a fresh grade B must beat the hit's stale state=blocked.
    #    apply_qa_gate then queue_entry is the only correct order; reversed, the
    #    merge copies state=blocked and qa=null back over the new verdict.
    vids = [{"key": "k", "state": "blocked", "qa": None, "video_url": "old"}]
    entry = {"key": "k", "state": "ready", "duration_sec": 7208.3, "video_url": "new"}
    A.apply_qa_gate(entry, receipt(12.0))
    A.queue_entry(vids, entry, receipt(12.0))
    want = qa_gate.grade(receipt(12.0))["grade"]
    got = (vids[0].get("qa") or {}).get("grade")
    check("a re-grade clears the stale blocked state in the manifest",
          vids[0]["state"] == "ready" and got == want,
          f'{vids[0]["state"]}/{got} (want {want})')

    # 7. Without a receipt the upload record is preserved (skip path).
    vids = [{"key": "k", "state": "published", "qa": {"grade": "B"}, "video_id": "abc"}]
    entry = {"key": "k", "state": "ready"}
    A.apply_qa_gate(entry, {})
    A.queue_entry(vids, entry, {})
    check("a no-receipt re-run keeps the live record",
          vids[0]["state"] == "published" and vids[0]["video_id"] == "abc"
          and vids[0]["qa"]["grade"] == "B", vids[0]["state"])

    # 8. A brand-new key is appended.
    vids = []
    check("a new key is added",
          A.queue_entry(vids, {"key": "new", "state": "ready"}, receipt(12.0)) == "added"
          and len(vids) == 1)

    if FAILS:
        print(f"\nFAILED: {FAILS}")
        return 1
    print("\nOK: the QA gate vetoes a weak build, never an absent one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
