#!/usr/bin/env python3
"""The owner-login helper must use the ADD-account flow and the right secret.

Option B needs ak to sign the pod's browser into a channel's OWNER account. Two
easy ways to get that silently wrong, both of which this guard catches:

  * using the plain sign-in URL -- when the browser is already signed in as
    someone else it just redirects to that account, so the new account is never
    added and the invite is made by the wrong person;
  * a transport that cannot wrap the named secret, or wraps it to nothing --
    fetch_secret.py then decrypts an empty string and the run fails with a
    confusing message.

This guard must be able to FAIL: it fails if the helper stops using AddSession, if
cred-transport stops reading the secret by name, or if it goes green on an empty
value.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    src = (ROOT / "scripts" / "pod_account_login.py").read_text(encoding="utf-8")
    if "AddSession" not in src:
        fail("pod_account_login.py no longer uses the AddSession flow; adding a "
             "second account would silently fall back to the signed-in one")
    m = re.search(r'SECRET\s*=\s*"([A-Z0-9_]+)"', src)
    if not m:
        fail("pod_account_login.py has no SECRET constant")
    secret = m.group(1)

    # The password must come from the secret store, never a literal in the file.
    if re.search(r'--password["\']?\s*,\s*["\']', src) or re.search(
            r"password\s*=\s*[\"'][^\"']{6,}[\"']", src):
        fail("pod_account_login.py appears to hardcode a password")

    wf = (ROOT / ".github" / "workflows" / "cred-transport.yml").read_text(encoding="utf-8")
    # The workflow used to hold a hand-written table mapping each secret name to an
    # env var. It now wraps whatever name the pod asks for, so the property worth
    # guarding changed: the job must read the secret by *name* (not a fixed list),
    # and must fail loudly when the name resolves to nothing -- otherwise
    # fetch_secret.py decrypts an empty string and reports a confusing error.
    if "secrets[inputs.secret_name]" not in wf:
        fail("cred-transport.yml no longer reads secrets[inputs.secret_name]; a "
             "secret added to the repo would not be wrappable by name")
    # The workflow has exactly one exit code, and it is a failure. This is checked
    # over the whole file rather than a slice, because a slice keyed on nearby text
    # silently widens if that text is reformatted (Gemini, 2026-11-19) -- and a
    # widened slice can pass while the real branch exits 0.
    if "EMPTY:" not in wf:
        fail("cred-transport.yml no longer reports an empty secret")
    exits = re.findall(r"(?:SystemExit|sys\.exit)\((\d+)\)", wf)
    if exits != ["1"]:
        fail(f"cred-transport.yml must fail the job on an empty secret and must not "
             f"exit 0 anywhere; found exit calls {exits}")
    # A green run can also come from the shell, not Python: `exit 0`, `|| echo 0`,
    # `|| true`, or a continue-on-error on the step would hide the same failure
    # (Gemini, 2026-11-19). The last two are this project's known false-pass shape.
    for pattern, why in (
        (r"^\s*exit\s+\d+", "a shell exit"),
        (r"\|\|\s*(true|echo\s+0|:)\b", "an `|| true` swallow"),
    ):
        hits = re.findall(pattern, wf, flags=re.M)
        if hits:
            fail(f"cred-transport.yml uses {why} {hits}; the job's status must come "
                 "from the Python exit code alone")
    if "continue-on-error" in wf:
        fail("cred-transport.yml sets continue-on-error; a failed wrap would read "
             "as a successful run")

    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    if "websocket-client" not in req:
        fail("requirements.txt does not pin websocket-client; a recycled pod loses "
             "it and every CDP helper dies with 'need websocket-client'")

    print(f"OK: pod_account_login uses AddSession and reads {secret}, which "
          "cred-transport wraps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
