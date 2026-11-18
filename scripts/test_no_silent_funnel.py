#!/usr/bin/env python3
"""A rail that cannot do its job must not report success.

Measured 2026-11-18: the shared Data-API pool was spent every day, so
`link_shorts.py` raised `403 quotaExceeded` on every channel -- and the workflow
ran it as `python3 scripts/link_shorts.py ... || true`, which swallowed the
traceback into a GREEN run. The Shorts -> long-form funnel was unwired and the
report said "all rails fresh". The same day `set_thumbnails.py --check` reported
12 live covers as "auto/other" because `videos.list` raised 403 and the old
`except: return ""` turned an unreadable state into a state.

This guard drives the REAL classifiers with REAL error shapes (no network) and
FAILS if a spent quota is classified as success, if `--check` reads an unreadable
API as "not ours", or if the workflow reintroduces `|| true`.

    python3 scripts/test_no_silent_funnel.py     # exit 0 = no silent pass
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import link_shorts as ls  # noqa: E402
import set_thumbnails as st  # noqa: E402

fails = 0


def check(name: str, ok: bool) -> None:
    global fails
    print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    if not ok:
        fails += 1


def _quota_error() -> urllib.error.HTTPError:
    body = json.dumps({"error": {"code": 403, "errors": [
        {"reason": "quotaExceeded", "message": "exceeded your quota"}]}}).encode()
    return urllib.error.HTTPError("u", 403, "Forbidden", {}, __import__("io").BytesIO(body))


def _rate_limit_error() -> urllib.error.HTTPError:
    body = json.dumps({"error": {"code": 429, "errors": [
        {"reason": "uploadRateLimitExceeded"}]}}).encode()
    return urllib.error.HTTPError("u", 429, "Too Many Requests", {}, __import__("io").BytesIO(body))


def _perm_error() -> urllib.error.HTTPError:
    body = json.dumps({"error": {"code": 403, "errors": [
        {"reason": "forbidden", "message": "insufficient permission"}]}}).encode()
    return urllib.error.HTTPError("u", 403, "Forbidden", {}, __import__("io").BytesIO(body))


def main() -> int:
    # 1. link_shorts: a spent pool is a DEFERRAL (exit 2), never green (exit 0).
    q = _quota_error()
    check("quota -> classify_reason 'deferred'",
          ls.classify_reason(ls._reason(q), q.code) == "deferred")
    rl = _rate_limit_error()
    check("rate limit -> 'deferred'",
          ls.classify_reason(ls._reason(rl), rl.code) == "deferred")
    perm = _perm_error()
    check("a real permission error -> 'failed'",
          ls.classify_reason(ls._reason(perm), perm.code) == "failed")
    check("a plain 500 -> 'failed'",
          ls.classify_reason("backendError", 500) == "failed")

    # 2. set_thumbnails: --check must raise on an unreadable read, not report
    #    "auto/other". A quota error inside current_thumbnail must propagate.
    orig_urlopen = st.urllib.request.urlopen

    def raising_urlopen(*a, **k):
        raise _quota_error()

    st.urllib.request.urlopen = raising_urlopen
    try:
        raised = False
        try:
            st.current_thumbnail("vid", "tok")
        except urllib.error.HTTPError:
            raised = True
        check("current_thumbnail RAISES on a spent quota (no false 'auto/other')", raised)

        # matches_live must NOT swallow it either -- an unreadable state is unknown.
        raised2 = False
        try:
            st.matches_live("vid", os.path.join(ROOT, "requirements.txt"), "tok")
        except urllib.error.HTTPError:
            raised2 = True
        check("matches_live propagates the read error (unknown != done)", raised2)
    finally:
        st.urllib.request.urlopen = orig_urlopen

    # 3. The workflow must not swallow the exit code again.
    wf = open(os.path.join(ROOT, ".github", "workflows", "link-shorts.yml"), encoding="utf-8").read()
    check("link-shorts.yml does NOT run the funnel with `|| true`",
          not re.search(r"link_shorts\.py[^\n]*\|\|\s*true", wf))
    check("link-shorts.yml propagates the funnel exit code",
          "exit \"$rc\"" in wf or "exit $rc" in wf)

    print(f"\n{'all checks passed' if not fails else f'{fails} check(s) FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
