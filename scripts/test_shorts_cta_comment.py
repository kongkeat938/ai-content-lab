#!/usr/bin/env python3
"""The Shorts CTA comment: posted and pinned for a public upload, safe otherwise.

The subscribe/long-form ask lives in the description, which a Shorts viewer never
opens. The pinned comment is the one CTA surface that shows on the Shorts screen,
so it is the conversion bridge (measured 2026-11-12: 1.93 subs per 1000 views,
worst on the fleet, while the same Shorts get 1000+ views). This guards the three
things that must hold:

  1. a public upload gets the comment posted AND pinned;
  2. a non-public upload posts nothing (a viewer cannot see it anyway);
  3. a 403 "insufficient scope" is reported with the one-time fix, never raised --
     an upload that already succeeded must not fail because a comment could not post.

A fake API client is required here: the test must not post to a live channel. It
exercises the real function body, only standing in for the network.

    python3 scripts/test_shorts_cta_comment.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import publish_shorts as ps  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


class FakeReq:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


def real_httperror(status, body):
    """A real googleapiclient HttpError, so the except clause is genuinely hit."""
    from googleapiclient.errors import HttpError
    import httplib2
    return HttpError(httplib2.Response({"status": status}), body.encode())


class FakeThreads:
    def __init__(self, calls, err=None):
        self.calls, self.err = calls, err

    def insert(self, part=None, body=None):
        self.calls.append(("insert", part, body))
        if self.err:
            return FakeReq(lambda: (_ for _ in ()).throw(self.err))
        return FakeReq(lambda: {"snippet": {"topLevelComment": {"id": "COMMENT1"}}})


class FakeComments:
    def __init__(self, calls):
        self.calls = calls

    def setModerationStatus(self, id=None, moderationStatus=None):
        self.calls.append(("pin", id, moderationStatus))
        return FakeReq(lambda: {})


class FakeYT:
    def __init__(self, err=None):
        self.calls = []
        self._threads = FakeThreads(self.calls, err)

    def commentThreads(self):
        return self._threads

    def comments(self):
        return FakeComments(self.calls)


def main() -> int:
    spec = ps.CHANNELS["dharma"]
    s = {"cta": "กดติดตามเพื่อรับธรรมะก่อนนอนทุกวัน"}

    print("a public upload posts the CTA comment and pins it")
    yt = FakeYT()
    note = ps.pin_cta_comment(yt, "VID1", spec, s, "public")
    kinds = [c[0] for c in yt.calls]
    check("comment inserted", kinds[:1] == ["insert"], str(kinds))
    check("comment pinned", "pin" in kinds, str(kinds))
    check("the note names the comment", "COMMENT1" in (note or ""), str(note))
    body = yt.calls[0][2]["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
    check("the body carries the subscribe CTA", "กดติดตาม" in body, body[:60])
    check("the body points at the durable playlist", "playlist?list=" in body, body[:80])

    print("a non-public upload posts nothing")
    yt2 = FakeYT()
    note2 = ps.pin_cta_comment(yt2, "VID2", spec, s, "private")
    check("no API calls for a private upload", yt2.calls == [], str(yt2.calls))
    check("the skip is reported", "skip" in (note2 or "").lower(), str(note2))

    print("a scope 403 is reported with the fix, never raised")
    yt3 = FakeYT(err=real_httperror(403, "Insufficient Permission: insufficient scope"))
    try:
        note3 = ps.pin_cta_comment(yt3, "VID3", spec, s, "public")
        check("no exception escapes", True)
        check("the note names the force-ssl fix", "force-ssl" in (note3 or ""), str(note3))
    except Exception as exc:  # noqa: BLE001
        check("no exception escapes", False, f"{type(exc).__name__}: {exc}")

    print("a non-scope error is reported but does not raise")
    yt4 = FakeYT(err=real_httperror(500, "backend error"))
    try:
        note4 = ps.pin_cta_comment(yt4, "VID4", spec, s, "public")
        check("no exception escapes on a 500", True)
        check("the failure is reported", "failed" in (note4 or ""), str(note4))
    except Exception as exc:  # noqa: BLE001
        check("no exception escapes on a 500", False, f"{type(exc).__name__}: {exc}")

    print("every publishing channel declares a pin_cta")
    for name in ("dharma", "genx"):
        check(f"{name} has a non-empty pin_cta", bool(ps.CHANNELS[name].get("pin_cta")))

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: the CTA comment posts+pins on a public upload and never breaks one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
