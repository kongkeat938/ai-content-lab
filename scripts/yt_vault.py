#!/usr/bin/env python3
"""Keep a channel's OAuth token in the durable KV vault, not on the pod.

The pod is recycled mid-session (measured 2026-11-26), and `~/.config/content-lab`
goes with it, so a token that lives only there forces the owner through OAuth
again. The vault survives the recycle and is read back with OPENHANDS_API_KEY.

    python3 scripts/yt_vault.py put --slug genx            # from ~/.config/content-lab
    python3 scripts/yt_vault.py status --slug genx
    python3 scripts/yt_vault.py get --slug genx --out FILE

The token is never printed: only a sha256 fingerprint, which is enough to tell
two tokens apart. One attempt per call -- a failure is reported, not retried.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

AID = "94068e1c-c98c-4f3b-96f5-0df4a1e9a78a"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_DIR = os.path.expanduser("~/.config/content-lab")


def key_for(slug: str) -> str:
    return f"yt.{slug}.refresh_token"


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def vault(method: str, key: str, value: dict | None = None) -> dict | None:
    api = os.environ.get("OPENHANDS_API_KEY") or os.environ.get("KONGKEAT_OH_KEY")
    if not api:
        raise SystemExit("no OPENHANDS_API_KEY/KONGKEAT_OH_KEY in the environment")
    url = f"https://app.all-hands.dev/api/automation/v1/kv/{key}?automation_id={AID}"
    body = json.dumps({"value": json.dumps(value)}).encode() if value is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Authorization": "Bearer " + api,
                                          "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=25)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"vault {method} failed: HTTP {exc.code}")
    except Exception as exc:                                   # noqa: BLE001
        raise SystemExit(f"vault {method} failed: {type(exc).__name__}")
    raw = r.read().decode()
    if method == "PUT":
        return {}
    try:
        doc = json.loads(raw).get("value")
        if isinstance(doc, str):
            doc = json.loads(doc)
        if isinstance(doc, dict) and isinstance(doc.get("value"), str):
            doc = json.loads(doc["value"])
    except Exception as exc:                                   # noqa: BLE001
        raise SystemExit(f"vault GET returned an unreadable body: {type(exc).__name__}")
    return doc if isinstance(doc, dict) else None


def source_path(slug: str) -> str:
    return os.path.join(TOKEN_DIR, f"yt_token_{slug}.json")


def guarded(path: str) -> None:
    """Refuse to read a token file that git would happily commit."""
    inside = os.path.abspath(path).startswith(os.path.abspath(ROOT) + os.sep)
    if not inside:
        return
    rel = os.path.relpath(path, ROOT)
    if subprocess.run(["git", "-C", ROOT, "check-ignore", "-q", rel]).returncode != 0:
        raise SystemExit(f"refusing: {rel} is inside the repo and not gitignored")


def cmd_put(args) -> int:
    path = args.file or source_path(args.slug)
    if not os.path.exists(path):
        raise SystemExit(f"no token file at {path}")
    guarded(path)
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    refresh = doc.get("refresh_token") or ""
    if not refresh:
        raise SystemExit("the token file holds no refresh_token")
    payload = {k: doc[k] for k in ("refresh_token", "client_id", "client_secret",
                                   "token_uri", "scopes") if k in doc}
    if args.channel_id:
        payload["channel_id"] = args.channel_id
    payload["slug"] = args.slug
    payload["saved_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    vault("PUT", key_for(args.slug), payload)
    back = vault("GET", key_for(args.slug)) or {}
    if back.get("refresh_token") != refresh:
        print(f"{args.slug} vault: fail - read-back did not match")
        return 1
    print(f"{args.slug} vault: ok (fp {fingerprint(refresh)})")
    return 0


def cmd_status(args) -> int:
    doc = vault("GET", key_for(args.slug)) or {}
    tok = doc.get("refresh_token") or ""
    if not tok:
        print(f"{args.slug} vault: absent")
        return 1
    print(f"{args.slug} vault: present (fp {fingerprint(tok)}, saved {doc.get('saved_utc','?')})")
    return 0


def cmd_get(args) -> int:
    doc = vault("GET", key_for(args.slug)) or {}
    tok = doc.get("refresh_token") or ""
    if not tok:
        print(f"{args.slug} vault: absent")
        return 1
    if not args.out:
        print(f"{args.slug} vault: present (fp {fingerprint(tok)}) -- pass --out to write it")
        return 0
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    print(f"{args.slug} vault: wrote {args.out} (mode 600, fp {fingerprint(tok)})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("put", cmd_put), ("get", cmd_get), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--slug", required=True)
        p.set_defaults(fn=fn)
        if name == "put":
            p.add_argument("--file")
            p.add_argument("--channel-id")
        if name == "get":
            p.add_argument("--out")
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
