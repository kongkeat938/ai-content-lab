#!/usr/bin/env python3
"""The owner-login helper must use the ADD-account flow and the right secret.

Option B needs ak to sign the pod's browser into a channel's OWNER account. Two
easy ways to get that silently wrong, both of which this guard catches:

  * using the plain sign-in URL -- when the browser is already signed in as
    someone else it just redirects to that account, so the new account is never
    added and the invite is made by the wrong person;
  * naming a secret that cred-transport.yml does not wrap -- fetch_secret.py then
    decrypts an empty string and the run fails with a confusing message.

This guard must be able to FAIL: it fails if the helper stops using AddSession, or
if the secret name and the transport table drift apart.
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
    if f"secrets.{secret}" not in wf:
        fail(f"cred-transport.yml does not map secrets.{secret}; fetch_secret.py "
             "would decrypt an empty value")
    if f'"{secret}":' not in wf:
        fail(f"cred-transport.yml does not add {secret} to its plaintext table")

    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    if "websocket-client" not in req:
        fail("requirements.txt does not pin websocket-client; a recycled pod loses "
             "it and every CDP helper dies with 'need websocket-client'")

    print(f"OK: pod_account_login uses AddSession and reads {secret}, which "
          "cred-transport wraps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
