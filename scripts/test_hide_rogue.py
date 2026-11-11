#!/usr/bin/env python3
"""Hiding a live rogue clip must be reversible and must never touch the backlog.

Measured 2026-11-11: a second upload stream (category 27, `en-US`, old brand)
inserts clips no manifest records. The response is to PAUSE them
(`privacyStatus=private`, reversible) -- never delete, and never touch a
historical pre-manifest upload, which may be a legitimate old video.

This guard must be able to FAIL: it fails if a delete is ever issued, if the
historical clip is hidden, or if the ledger is not idempotent.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_channels as ac  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


class FakeVideos:
    def __init__(self, log):
        self.log = log

    def update(self, part, body):
        self.log.append(("update", body["id"], body["status"]["privacyStatus"]))
        return self

    def delete(self, **kw):
        self.log.append(("DELETE", kw))
        return self

    def execute(self):
        return {}


class FakeYT:
    def __init__(self, log):
        self._v = FakeVideos(log)

    def videos(self):
        return self._v


LIVE = ("video ROGUE1 is UNRECORDED and published 0.3d ago "
        "-- LIVE rogue upload outside the rails: คลิปเถื่อน")
OLD = ("video OLD1 is on the channel but in NO manifest "
       "(historical, pre-manifest): คลิปเก่า")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "scripts").mkdir()
    (tmp / "content").mkdir()
    real_here, real_client, real_comment = ac.HERE, ac.client_for, ac._comment_hidden
    log, comments = [], []
    ac.HERE = str(tmp / "scripts")           # root = tmp
    ac.client_for = lambda slug, cid: FakeYT(log)
    ac._comment_hidden = lambda newly: comments.append(newly)

    report = {"kongkeat-story": {"channel": {"id": "UC4"}, "defects": [LIVE, OLD]}}
    try:
        ac.hide_live_rogue(report)

        updates = [x for x in log if x[0] == "update"]
        if len(updates) != 1 or updates[0][1] != "ROGUE1":
            fail(f"expected exactly one update for ROGUE1, got {updates}")
        if updates[0][2] != "private":
            fail(f"a rogue clip must be set private (reversible), got {updates[0][2]}")
        if any(x[0] == "DELETE" for x in log):
            fail("a delete was issued; hiding must never delete (not reversible)")
        if any("OLD1" in str(x) for x in log):
            fail("the historical pre-manifest clip was touched; it may be legitimate")

        led = json.load(open(tmp / "content" / "rogue_hidden.json", encoding="utf-8"))
        if [h["video_id"] for h in led["hidden"]] != ["ROGUE1"]:
            fail(f"ledger is wrong: {led}")
        if not comments:
            fail("the take-down was not reported on the alert issue")

        # Idempotent: a second run must not re-hide or re-append.
        ac.hide_live_rogue(report)
        if len([x for x in log if x[0] == "update"]) != 1:
            fail("a re-run re-hid an already-hidden clip; the ledger is not respected")
        led2 = json.load(open(tmp / "content" / "rogue_hidden.json", encoding="utf-8"))
        if len(led2["hidden"]) != 1:
            fail("the ledger grew on a re-run; it must be idempotent")

        # A transient read-quota 403 must NOT close the alert: measuring nothing
        # is not "the rogue stream is gone". Trap `gh` and assert it is not called
        # to close the issue.
        calls = []

        class FakeRun:
            stdout = json.dumps([{"number": 22,
                                  "title": "Channel audit: a live upload stream outside the rails"}])
            returncode = 0

            def __call__(self, *a, **k):
                calls.append(a[0] if a else k)
                return self

        real_run = ac.subprocess.run
        ac.subprocess.run = FakeRun()
        try:
            ac.alert_live_rogue({"genx": {"error": "quotaExceeded"},
                                 "dharma": {"error": "quotaExceeded"},
                                 "kongkeat-story": {"error": "quotaExceeded"}})
        finally:
            ac.subprocess.run = real_run
        if any(c and c[0] == "gh" and "close" in c for c in calls):
            fail("the alert closed the issue on an all-error report; a spent quota "
                 "must not be read as 'no rogue stream'")

        print("OK: a live rogue clip is set private (never deleted), the backlog is "
              "untouched, the ledger is idempotent, and an all-error report never "
              "closes the alert")
        return 0
    finally:
        ac.HERE, ac.client_for, ac._comment_hidden = real_here, real_client, real_comment


if __name__ == "__main__":
    sys.exit(main())
