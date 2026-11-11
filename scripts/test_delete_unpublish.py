#!/usr/bin/env python3
"""Unpublishing a bad cut must be reversible and must never delete.

Measured 2026-11-11: the guarded delete refused a video with views and retried
~37 times in a day, leaving a 57-minute static-card cut (Reused-Content risk)
public. The fix is `--unpublish`: set it private (reversible), which is not gated
on `--max-views`, and write the `.done` marker so the rail stops retrying.

This guard must be able to FAIL: it fails if a delete is issued, if the marker is
not written, if a dry run changes anything, or if the workflow still deletes.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import delete_video as dv  # noqa: E402

VID = "HkbSguA53ro"
ROW = {
    "id": VID,
    "snippet": {"title": "นิทานธรรมะสอนใจ ทางสายกลาง"},
    "status": {"privacyStatus": "public"},
    "contentDetails": {"duration": "PT57M6S"},
    "statistics": {"viewCount": "53"},
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def run(argv, tmp, log):
    real = (dv.publish_batch.access_token, dv.get, dv.set_private, dv.delete, dv.BACKUP_DIR)
    dv.publish_batch.access_token = lambda slug: "tok"
    dv.get = lambda tok, vid: dict(ROW)
    dv.set_private = lambda tok, vid: (log.append(("private", vid)), (200, ""))[1]
    dv.delete = lambda tok, vid: (log.append(("DELETE", vid)), (200, ""))[1]
    dv.BACKUP_DIR = str(tmp / "deleted")
    real_argv = sys.argv
    sys.argv = ["delete_video.py"] + argv
    try:
        return dv.main()
    finally:
        (dv.publish_batch.access_token, dv.get, dv.set_private, dv.delete, dv.BACKUP_DIR) = real
        sys.argv = real_argv


def main() -> int:
    tmp = Path(tempfile.mkdtemp())

    # 1. --unpublish without --yes is a dry run: nothing happens, no marker.
    log = []
    run(["--slug", "dharma", "--video", VID, "--unpublish"], tmp, log)
    if log:
        fail(f"a dry run changed something: {log}")
    if (tmp / "deleted" / f"{VID}.done").exists():
        fail("a dry run wrote the .done marker")

    # 2. --unpublish --yes sets private (not delete), even with 53 views, and
    #    writes the marker so the rail stops retrying.
    log = []
    run(["--slug", "dharma", "--video", VID, "--unpublish", "--yes"], tmp, log)
    if log != [("private", VID)]:
        fail(f"expected exactly one private call and no delete, got {log}")
    if any(x[0] == "DELETE" for x in log):
        fail("a delete was issued; --unpublish must never delete (not reversible)")
    if not (tmp / "deleted" / f"{VID}.done").exists():
        fail("the .done marker was not written; the rail would retry forever")

    # 3. The workflow must call --unpublish, not a bare delete.
    wf = (Path(__file__).resolve().parent.parent
          / ".github" / "workflows" / "remove-bad-cut.yml").read_text(encoding="utf-8")
    if "--unpublish" not in wf:
        fail("remove-bad-cut.yml still deletes instead of unpublishing")

    print("OK: a bad cut is unpublished (private, reversible, not gated on views), "
          "never deleted, the marker stops the retry loop, and the rail uses it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
