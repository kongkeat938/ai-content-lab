#!/usr/bin/env python3
"""Is PC1 (K's Windows machine) reachable, and if not, why?

K's inbox cannot be read from this sandbox: Google refuses a sign-in from the pod
browser ("This browser or app may not be secure", measured 2026-11-08), and an app
password is not something K can create. The one place the mail *is* readable is PC1:
its Chrome is already signed into all four accounts and reads them through Gmail's
Atom feed. So the whole mail layer hangs on one question -- is PC1 up? -- and when it
is down that must be visible, not silent.

This answers the question and names the exact recovery, so the break is actionable
instead of a mystery. It does not need the token to tell "offline" from "up"; the
token only turns a 401 into "the key differs" rather than "unknown".

    PC1_MCP_URL=https://<host>/mcp python3 scripts/pc1_health.py
    python3 scripts/pc1_health.py --strict   # exit 1 when PC1 is down

The URL is a secret (a public repo must not carry the funnel), so it comes from the
environment. Nothing here prints the token.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT = os.path.join(ROOT, "docs", "PC1-HEALTH.md")

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "pc1-health", "version": "1"}}}


def probe(url: str, token: str | None, timeout: int = 25) -> tuple[str, str]:
    """Return (verdict, detail). verdict is 'up', 'backend-down', 'auth', or 'offline'.

    The verdicts are split because they need different fixes: an offline host needs a
    human at the machine, a backend-down host needs the winremote server restarted,
    and a bad token needs the secret corrected. Collapsing them into one 'down' would
    hide which of the three it is.
    """
    body = json.dumps(INIT).encode()
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read(400).decode("utf-8", "replace")
            return "up", f"HTTP {resp.status}; {text[:120]}"
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return "auth", "HTTP 401 -- the host answered; PC1_MCP_TOKEN is wrong or stale"
        if exc.code in (502, 503, 504):
            return ("backend-down",
                    f"HTTP {exc.code} -- the funnel is up but the winremote MCP backend "
                    f"(127.0.0.1:8090) is not running; only a human at PC1 can restart it")
        return "down", f"HTTP {exc.code} {exc.read(160).decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001 - any failure must be reported, not hidden
        return "offline", f"{type(exc).__name__}: {str(exc)[:140]}"


RECOVERY = {
    "up": "PC1 is reachable; the inbox layer can run.",
    "backend-down": ("At PC1, run:  ops\\pc1_fix_remote.ps1 -Token <PC1_MCP_TOKEN> -Persist  "
                     "(restarts the winremote MCP server so it also survives a reboot)"),
    "auth": "Set the PC1_MCP_TOKEN secret to the current value and re-run.",
    "offline": ("Turn PC1 on and keep it awake, or run the reader at the machine:  "
                "C:\\ax-work\\_ax\\readbox.ps1 -Profile \"Profile 3\" -Label ch2  "
                "(Chrome there is already signed into all four accounts)"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("PC1_MCP_URL", ""))
    ap.add_argument("--write", action="store_true", help="write docs/PC1-HEALTH.md")
    ap.add_argument("--strict", action="store_true", help="exit 1 unless PC1 is up")
    args = ap.parse_args()

    if not args.url:
        print("PC1_MCP_URL is not set -- cannot probe PC1 (the funnel URL is a secret)")
        return 1 if args.strict else 0

    verdict, detail = probe(args.url, os.environ.get("PC1_MCP_TOKEN"))
    line = f"PC1: {verdict} -- {detail}"
    print(line)
    print(f"  next: {RECOVERY.get(verdict, 'see the detail above')}")

    if args.write:
        with open(REPORT, "w", encoding="utf-8") as fh:
            fh.write(f"# PC1 health\n\n- **{verdict}** -- {detail}\n- next: "
                     f"{RECOVERY.get(verdict, 'see above')}\n")

    return 1 if (args.strict and verdict != "up") else 0


if __name__ == "__main__":
    raise SystemExit(main())
