#!/usr/bin/env python3
"""A check that cannot read the comment must say so, and must still write it down.

The first cut loaded the credential outside the try block, so a dead token
exited 1 with a traceback and left no record at all: "could not read" and
"still fine" looked the same to anyone reading the ledger later.

    python3 scripts/test_watch_comment.py
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

import watch_comment as w  # noqa: E402


class FakeYt:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def comments(self):
        return self

    def list(self, **kw):
        self.calls.append(kw)
        return self

    def execute(self):
        if self.error:
            raise self.error
        return {"items": [{"snippet": {"textDisplay": self.text}}] if self.text else []}


class HttpBoom(Exception):
    class resp:  # noqa: N801 - mimic googleapiclient's shape
        status = 403


CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def run(tmp, *, yt=None, creds_error=None, label="1h"):
    """Run main() with the API stubbed; the ledger goes to a temp file."""
    import yt_auth
    import googleapiclient.discovery as discovery

    def load_credentials(*_a, **_k):
        if creds_error:
            raise creds_error
        return object()

    orig = (yt_auth.load_credentials, discovery.build, w.LEDGER)
    yt_auth.load_credentials = load_credentials
    discovery.build = lambda *a, **k: yt
    w.LEDGER = os.path.join(tmp, "comment_watch_{slug}.json")
    argv, out, err = sys.argv, io.StringIO(), io.StringIO()
    sys.argv = ["watch_comment.py", "--slug", "dharma", "--label", label, "--json"]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = w.main()
    finally:
        yt_auth.load_credentials, discovery.build, w.LEDGER = orig
        sys.argv = argv
    path = os.path.join(tmp, "comment_watch_dharma.json")
    log = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    return code, log, out.getvalue(), err.getvalue()


def main() -> int:
    tmp = tempfile.mkdtemp()

    # 1. the bug: a dead credential used to exit 1 with a traceback and no record
    code, log, out, err = run(tmp, creds_error=RuntimeError("no refresh token"))
    check("dead credential -> exit 2 (not 1)", code == 2, str(code))
    check("dead credential still writes a ledger record", len(log) == 1, str(len(log)))
    check("record says blind", (log or [{}])[0].get("state") == "blind", str(log[:1]))
    check("record names the failure without the value",
          "auth failed: RuntimeError" == (log or [{}])[0].get("detail"),
          str((log or [{}])[0].get("detail")))
    check("no traceback on stderr", "Traceback" not in err, err[-120:])

    # 1b. the real failure mode: yt_auth exits instead of raising
    tmp1b = tempfile.mkdtemp()
    code, log, _out, err = run(tmp1b, creds_error=SystemExit(f"No saved token at {os.path.expanduser('~')}/.config/content-lab/yt_token.json."))
    check("auth helper that sys.exit()s -> exit 2, not 1", code == 2, str(code))
    check("that path also writes a ledger record", len(log) == 1, str(len(log)))
    check("home path is masked in the detail",
          os.path.expanduser("~") not in str((log or [{}])[0].get("detail")),
          str((log or [{}])[0].get("detail")))
    check("the reason survives", "No saved token" in str((log or [{}])[0].get("detail")),
          str((log or [{}])[0].get("detail")))

    # 2. a query that fails is BLIND, never "absent"
    tmp2 = tempfile.mkdtemp()
    code, log, _out, _err = run(tmp2, yt=FakeYt(error=HttpBoom()))
    check("query failure -> exit 2", code == 2, str(code))
    check("query failure is blind, not absent", (log or [{}])[0].get("state") == "blind",
          str(log[:1]))
    check("query failure records the HTTP status",
          "HTTP 403" in str((log or [{}])[0].get("detail")), str((log or [{}])[0].get("detail")))

    # 3. the happy path still works, and a changed text is 'edited'
    tmp3 = tempfile.mkdtemp()
    code, log, _out, _err = run(tmp3, yt=FakeYt(text="full offer PLBpZCGnd7Q5Y here"))
    check("present + marker -> exit 0", code == 0, str(code))
    check("present recorded", (log or [{}])[0].get("state") == "present", str(log[:1]))

    tmp4 = tempfile.mkdtemp()
    code, log, _out, _err = run(tmp4, yt=FakeYt(text="the link was removed"))
    check("missing marker -> exit 2", code == 2, str(code))
    check("edited recorded", (log or [{}])[0].get("state") == "edited", str(log[:1]))

    # 4. appending, never overwriting
    tmp5 = tempfile.mkdtemp()
    run(tmp5, yt=FakeYt(text="PLBpZCGnd7Q5Y"), label="1h")
    code, log, _out, _err = run(tmp5, yt=FakeYt(text="PLBpZCGnd7Q5Y"), label="6h")
    check("two checks append, none is lost", len(log) == 2, str(len(log)))
    check("both labels kept", [r.get("label") for r in log] == ["1h", "6h"], str(log))

    bad = [n for n, ok, _ in CHECKS if not ok]
    print()
    print(f"{len(CHECKS) - len(bad)}/{len(CHECKS)} checks passed" if not bad
          else f"FAIL: {len(bad)} check(s): {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
