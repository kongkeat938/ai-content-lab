#!/usr/bin/env python3
"""measure_d10 must survive both baseline shapes and never guess a window.

Two bugs shipped in the first cut:
  * `shorts_feed_views` is sometimes an int and sometimes the whole
    {source: views} dict (the probe that wrote the baseline stored both), so
    `now - before` raised TypeError on F4qFHoVpEyI and RJPCYx_DUqU.
  * A window whose start is after its end queried nothing and then printed
    "ALL ZERO", which reads as a verdict. It must be BLIND instead.

    python3 scripts/test_measure_d10.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import measure_d10 as m  # noqa: E402


class FakeYta:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows, error, []

    def reports(self):
        return self

    def query(self, **kw):
        self.calls.append(kw)
        return self

    def execute(self):
        if self.error:
            raise self.error
        return {"rows": self.rows or []}


def http_error(status=500):
    from googleapiclient.errors import HttpError
    import httplib2
    resp = httplib2.Response({"status": status})
    resp.reason = "boom"
    return HttpError(resp, b'{"error":{"code":%d,"message":"boom"}}' % status)


def baseline(path, posted="2026-11-26"):
    doc = {
        "test_comment": {"posted_utc": posted + "T04:52Z"},
        "d10_top5_longforms": [
            {"video_id": "AAAAAAAAAAA", "title": "int shape", "views": 100,
             "shorts_feed_views": 0},
            {"video_id": "BBBBBBBBBBB", "title": "dict shape", "views": 200,
             "shorts_feed_views": {"SUBSCRIBER": 272, "RELATED_VIDEO": 92}},
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def run(path, yta):
    import yt_auth
    import googleapiclient.discovery as discovery
    orig = (yt_auth.load_credentials, discovery.build)
    yt_auth.load_credentials = lambda *a, **k: object()
    discovery.build = lambda *a, **k: yta
    argv, out = sys.argv, io.StringIO()
    sys.argv = ["measure_d10.py", "--baseline", path, "--json"]
    try:
        with contextlib.redirect_stdout(out):
            try:
                code = m.main()
            except SystemExit as exc:
                code = exc.code
            except Exception as exc:                      # noqa: BLE001
                code = f"CRASH {type(exc).__name__}: {exc}"
    finally:
        yt_auth.load_credentials, discovery.build = orig
        sys.argv = argv
    return code, out.getvalue()


CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def main() -> int:
    tmp = tempfile.mkdtemp()

    p = baseline(os.path.join(tmp, "b1.json"))
    code, out = run(p, FakeYta(rows=[["SHORTS", 5]]))
    check("gained>0 -> exit 0", code == 0, str(code))
    rows = {}
    with contextlib.suppress(Exception):
        rows = {r["video_id"]: r for r in json.loads(out)["rows"]}
    check("dict shape gives before=0", rows.get("BBBBBBBBBBB", {}).get("shorts_before") == 0,
          str(rows.get("BBBBBBBBBBB")))
    check("dict shape does not crash the run", "CRASH" not in str(code), str(code))
    check("delta counted against 0", rows.get("BBBBBBBBBBB", {}).get("delta") == 5,
          str(rows.get("BBBBBBBBBBB")))

    p = baseline(os.path.join(tmp, "b2.json"))
    code, _ = run(p, FakeYta(error=http_error()))
    check("query failure -> exit 2 (BLIND)", code == 2, str(code))

    p = baseline(os.path.join(tmp, "b4.json"))
    code, _ = run(p, FakeYta(rows=[["SHORTS", 0]]))
    check("no gain at all -> exit 3 (ALL ZERO)", code == 3, str(code))

    p = baseline(os.path.join(tmp, "b5.json"))
    code, _ = run(p, FakeYta(rows=[]))
    check("empty report is a zero gain, not a crash -> exit 3", code == 3, str(code))

    p = baseline(os.path.join(tmp, "b3.json"), posted="2099-01-01")
    fake = FakeYta(rows=[["SHORTS", 0]])
    code, out = run(p, fake)
    check("window with start>end -> exit 2", code == 2, str(code))
    check("that window never queried", not fake.calls, f"{len(fake.calls)} call(s)")
    check("no ALL ZERO verdict from a dead window", "ALL ZERO" not in out, out[:80])

    bad = [n for n, ok, _ in CHECKS if not ok]
    print()
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed" if not bad
          else f"FAIL: {len(bad)} check(s): {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
