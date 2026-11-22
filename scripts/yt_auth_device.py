"""Google login from the phone in 20 seconds -- no noVNC, no PC1.

K (2026-11-22): "I work from a phone. In noVNC I cannot scroll or zoom, and
reaching the password field is a fight." So the browser moved off the pod
entirely: Google's device flow hands ak a short code, K opens
`https://www.google.com/device` on the phone, types eight characters and taps
Allow -- the phone's own autofill and biometrics do the rest.

    python3 scripts/yt_auth_device.py --slug ch2            # default scopes
    python3 scripts/yt_auth_device.py --scopes force-ssl    # + comments

Measured 2026-11-22: the existing OAuth client answers `/device/code` with 200,
so no console change is needed. The refresh token is written 0600 by
`yt_auth.save_token`; it is never printed (only a fingerprint).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import yt_auth  # noqa: E402

DEVICE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
VERIFY_URL = "https://www.google.com/device"
PENDING = {"authorization_pending", "slow_down"}


class DeviceError(RuntimeError):
    """A terminal device-flow failure; the code names it."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _post(url: str, data: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}


def start(scope: str, client: dict) -> dict:
    status, body = _post(DEVICE_URL, {"client_id": client["client_id"], "scope": scope})
    if status != 200 or "user_code" not in body:
        raise DeviceError(body.get("error") or f"device/code HTTP {status}")
    return body


def poll(device: dict, client: dict, timeout: float | None = None,
         sleep=time.sleep, now=time.time) -> dict:
    """Wait for K to approve. Raises DeviceError on any terminal answer."""
    interval = float(device.get("interval", 5))
    deadline = now() + float(timeout or device.get("expires_in", 1800))
    while True:
        if now() >= deadline:
            raise DeviceError("expired_token")
        sleep(interval)
        status, body = _post(TOKEN_URL, {
            "client_id": client["client_id"],
            "client_secret": client.get("client_secret", ""),
            "device_code": device["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        if status == 200 and body.get("access_token"):
            return body
        err = body.get("error", f"HTTP {status}")
        if err == "slow_down":
            interval += 5
            continue
        if err in PENDING:
            continue
        raise DeviceError(err)


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def channel_of(access_token: str) -> dict:
    """The channel this token owns, or {} when the quota is spent."""
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        headers={"Authorization": "Bearer " + access_token})
    try:
        body = json.load(urllib.request.urlopen(req, timeout=25))
    except Exception:                                   # noqa: BLE001 - quota/403 is not fatal
        return {}
    items = body.get("items") or []
    return items[0] if items else {}


def oauth_client() -> dict:
    """The OAuth client: the split env pair first (measured device-flow capable
    2026-11-22), then the whole JSON secret."""
    pair = yt_auth.client_from_env()
    if pair:
        return {"client_id": pair[0], "client_secret": pair[1]}
    try:
        c = yt_auth.load_client_secrets(None)
    except SystemExit:
        raise SystemExit("No OAuth client: set YT_CLIENT_ID/YT_CLIENT_SECRET or CLIENT_SECRET")
    return {"client_id": c["client_id"], "client_secret": c.get("client_secret", "")}


def announce(device: dict) -> None:
    print("1) เปิดบนมือถือ: " + VERIFY_URL, flush=True)
    print("2) พิมพ์รหัส: " + device["user_code"], flush=True)
    print("3) เลือกบัญชี Google ของช่องนี้ แล้วกด 'อนุญาต'", flush=True)
    print(f"   (รหัสหมดอายุใน {int(device.get('expires_in', 1800)) // 60} นาที)", flush=True)


def main() -> int:
    ap = __import__("argparse").ArgumentParser(description=__doc__)
    ap.add_argument("--scopes", default="default", choices=sorted(yt_auth.SCOPE_SETS))
    ap.add_argument("--slug", help="write yt_token_<slug>.json (as yt_auth --slug does)")
    ap.add_argument("--code-file", help="also write the device code here, for --resume")
    ap.add_argument("--resume", help="poll with a device code saved earlier")
    args = ap.parse_args()
    if args.slug:
        yt_auth.TOKEN_PATH = os.path.join(os.path.dirname(yt_auth.TOKEN_PATH),
                                          f"yt_token_{args.slug}.json")
    client = oauth_client()
    scope = " ".join(yt_auth.SCOPE_SETS[args.scopes])
    try:
        if args.resume:
            with open(args.resume, encoding="utf-8") as fh:
                device = json.load(fh)
        else:
            device = start(scope, client)
            announce(device)
            if args.code_file:
                with open(args.code_file, "w", encoding="utf-8") as fh:
                    json.dump(device, fh)
                os.chmod(args.code_file, 0o600)
        token = poll(device, client)
    except DeviceError as e:
        print(f"FAILED: {e.code} -- ไม่ได้สิทธิ์ (ลองใหม่: เปิดคำสั่งเดิมอีกครั้ง)", flush=True)
        return 2 if e.code == "access_denied" else 3
    from google.oauth2.credentials import Credentials
    creds = Credentials(token=token["access_token"],
                        refresh_token=token.get("refresh_token"),
                        token_uri=TOKEN_URL,
                        client_id=client["client_id"],
                        client_secret=client.get("client_secret"),
                        scopes=token.get("scope", scope).split())
    ch = channel_of(token["access_token"])
    path = yt_auth.save_token(creds, ch or None)
    print(f"OK | channel: {ch.get('snippet', {}).get('title', '(quota spent: no stamp)')}"
          f" | id: {ch.get('id', '?')} | refresh {fingerprint(creds.refresh_token or '')}"
          f" | saved {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
