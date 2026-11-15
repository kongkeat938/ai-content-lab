#!/usr/bin/env python3
"""Guard the learning loop against a transient Analytics failure.

Measured 2026-11-15: `studio_ai.report()` called the Analytics API with a bare
`urllib.request.urlopen`. A one-off "HTTP Error 500: Internal Server Error" from
the endpoint killed the whole matrix job for ch1 while the other channels passed,
so `content/insights/ch1.json` was never written and the script generator was fed
stale data. A 5xx there is the API having a bad moment, not a bad request.

This test locks the contract:

  * a transient 5xx / 429 / timeout is retried (up to studio_ai.RETRIES) and the
    first success is returned;
  * a real 4xx (e.g. 400/403) is NOT retried -- it raises on the first call;
  * if every attempt fails, report() raises (so the job fails) rather than
    returning an empty result and letting a partial insights file be written.

This guard can FAIL: drop the retry loop (call urlopen once) and case 1 exits 1.

    python3 scripts/test_studio_retry.py     # exit 0 = a blip cannot lose a channel
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import studio_ai  # noqa: E402


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


def set_urlopen(fn):
    studio_ai.urllib.request.urlopen = fn


def main() -> int:
    real = studio_ai.urllib.request.urlopen
    real_sleep = studio_ai.time.sleep
    studio_ai.time.sleep = lambda *_a: None  # no real backoff in the test
    try:
        # 1. two 500s then success -> retried, returns the data
        seq = [http_error(500), http_error(500), FakeResp(json.dumps({"ok": 1}).encode())]
        calls = {"n": 0}

        def flaky(*_a, **_k):
            calls["n"] += 1
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        set_urlopen(flaky)
        got = studio_ai.report("tok", {})
        if got != {"ok": 1}:
            fail(f"retry did not return the eventual success: {got!r}")
        if calls["n"] != 3:
            fail(f"expected 3 attempts (2 failures + success), got {calls['n']}")
        print(f"OK: a transient 5xx is retried and recovers (attempts={calls['n']})")

        # 2. a real 4xx is NOT retried -> raises on the first call
        calls2 = {"n": 0}

        def bad_request(*_a, **_k):
            calls2["n"] += 1
            raise http_error(400)

        set_urlopen(bad_request)
        try:
            studio_ai.report("tok", {})
            fail("a 400 should raise, not be retried into a value")
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                fail(f"wrong error propagated: {exc.code}")
        if calls2["n"] != 1:
            fail(f"a 400 must not be retried; urlopen called {calls2['n']} times")
        print("OK: a real 4xx fails on the first call (no pointless retry)")

        # 3. every attempt fails -> raises (never returns an empty result)
        calls3 = {"n": 0}

        def always_500(*_a, **_k):
            calls3["n"] += 1
            raise http_error(503)

        set_urlopen(always_500)
        try:
            studio_ai.report("tok", {})
            fail("report() returned after every attempt failed -- must raise")
        except urllib.error.HTTPError:
            pass
        if calls3["n"] != studio_ai.RETRIES:
            fail(f"expected {studio_ai.RETRIES} attempts, got {calls3['n']}")
        print(f"OK: persistent failure raises after {calls3['n']} attempts (no empty result)")
    finally:
        studio_ai.urllib.request.urlopen = real
        studio_ai.time.sleep = real_sleep

    print("OK: the learning loop survives a transient Analytics blip and still FAILS loudly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
