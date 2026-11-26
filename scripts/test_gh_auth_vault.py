#!/usr/bin/env python3
"""An unreadable vault must not look like an empty one.

Measured 2026-11-26: `gh_auth.py status` printed "no token: none" while the vault
did hold a token -- the read had failed and `_vault()` swallowed the exception.
That sent the wrong instruction to K ("give me a token") for a problem that was
a failed read. This test fails if the two cases ever collapse again.

    python3 scripts/test_gh_auth_vault.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

os.environ.setdefault("OPENHANDS_API_KEY", "test-key-not-real")
import gh_auth  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


class FakeResponse(io.BytesIO):
    status = 200

    def read(self, *a):
        return super().read(*a)


def with_vault(behaviour):
    """Run _vault with urlopen replaced by `behaviour`."""
    real = gh_auth.urllib.request.urlopen
    gh_auth.urllib.request.urlopen = behaviour
    try:
        return gh_auth._vault("GET")
    finally:
        gh_auth.urllib.request.urlopen = real


def main() -> int:
    # 1. The vault answers, and holds a token.
    payload = json.dumps({"value": json.dumps({"token": "abc"})}).encode()
    got = with_vault(lambda *a, **k: FakeResponse(payload))
    check(got == {"token": "abc"}, "a readable vault returns its token")
    check(gh_auth.vault_reason() == "", "and reports no problem")

    # 2. The vault answers, but holds nothing.
    got = with_vault(lambda *a, **k: FakeResponse(json.dumps({"value": None}).encode()))
    check(got is None, "an empty vault returns None")
    check("no value stored" in gh_auth.vault_reason(), "and says so, rather than staying silent")

    # 3. The read fails -- this is the case that lied.
    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 500, "Server Error", {}, io.BytesIO(b""))

    got = with_vault(boom)
    check(got is None, "a failed read returns None")
    reason = gh_auth.vault_reason()
    check("unreadable" in reason and "500" in reason,
          f"and says it could not read (got {reason!r})")
    check(reason != "no value stored", "a failed read is not reported as an empty vault")

    # 4. A network drop is also "unreadable", never "empty".
    def drop(*a, **k):
        raise urllib.error.URLError("no route")

    with_vault(drop)
    check("unreadable" in gh_auth.vault_reason(), "a network drop is unreadable, not empty")

    # 5. A body that is not JSON is unreadable too.
    with_vault(lambda *a, **k: FakeResponse(b"<html>oops</html>"))
    check("unreadable" in gh_auth.vault_reason(), "a malformed body is unreadable")

    print()
    if failures:
        print(f"FAILED: {len(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
