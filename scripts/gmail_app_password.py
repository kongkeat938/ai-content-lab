#!/usr/bin/env python3
"""Create a Gmail app password from inside the pod, with no machine of K's involved.

The inbox is only readable over IMAP, and Gmail refuses a normal password there --
it wants an app password. Creating one needs a signed-in Google session, and the
pod's headless browser is turned away ("This browser or app may not be secure",
measured 2026-11-08). A real Chromium on a virtual display is not turned away: it
reached the password page for a real account (measured the same day). So this drives
that browser over the DevTools protocol: sign in, open the app-password page, name a
password, read the sixteen characters back, and store them.

    # one account
    GMAIL_USER=kongkeat.938@gmail.com GMAIL_PASSWORD=... python3 scripts/gmail_app_password.py
    # with a 2FA code (re-run with a fresh code if the first try times out)
    ... GMAIL_TOTP=123456 python3 scripts/gmail_app_password.py

    # every account, writing the secret in one step
    python3 scripts/gmail_app_password.py --accounts-file accounts.json --store

The password is never printed to a log by default -- it goes to the secret store, or
to a file outside the repository with --out. Google shows an app password only once,
so if it is lost, delete it and make another.

Requires: scripts/pod_chrome.sh running (it prints the CDP endpoint), and
websocket-client (pip install websocket-client).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

try:
    import websocket  # websocket-client
except ImportError:
    sys.exit("need websocket-client:  pip install websocket-client")

SIGNIN = "https://accounts.google.com/signin/v2/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
APPPW = "https://myaccount.google.com/apppasswords"


class Chrome:
    """A thin CDP client: enough to sign in and click, and nothing more."""

    def __init__(self, port: int = 9222):
        self.port = port
        self._id = 0
        self.ws = self._connect()

    def _connect(self):
        for _ in range(20):
            try:
                tabs = json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json", timeout=5))
                pages = [t for t in tabs if t.get("type") == "page"]
                if pages:
                    ws = websocket.create_connection(
                        pages[0]["webSocketDebuggerUrl"], timeout=60)
                    self._send(ws, "Page.enable")
                    self._send(ws, "Runtime.enable")
                    return ws
            except Exception:
                time.sleep(1)
        raise SystemExit("no Chromium on the CDP port; run scripts/pod_chrome.sh first")

    def _send(self, ws, method, params=None):
        self._id += 1
        ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == self._id:
                return msg

    def cmd(self, method, params=None):
        return self._send(self.ws, method, params)

    def nav(self, url, settle: float = 3.0):
        self.cmd("Page.navigate", {"url": url})
        time.sleep(settle)

    def js(self, expr):
        r = self.cmd("Runtime.evaluate",
                     {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")

    def wait_js(self, expr, timeout: float = 25.0, poll: float = 0.7):
        end = time.time() + timeout
        while time.time() < end:
            if self.js(expr):
                return True
            time.sleep(poll)
        return False

    def type_into(self, selector: str, text: str) -> bool:
        """Focus the field, then insert text as a real edit.

        Input.insertText is used rather than assigning .value because Google's
        sign-in reads keystrokes: a bare assignment can leave its validator unhappy
        and the Next button inert.
        """
        if not self.wait_js(f"!!document.querySelector({selector!r})", timeout=20):
            return False
        self.js(f"document.querySelector({selector!r}).focus()")
        self.cmd("Input.insertText", {"text": text})
        time.sleep(0.4)
        return True

    def click(self, selector: str) -> bool:
        if not self.wait_js(f"!!document.querySelector({selector!r})", timeout=15):
            return False
        self.js(f"document.querySelector({selector!r}).click()")
        time.sleep(1.2)
        return True


def page_text(c: Chrome) -> str:
    return c.js("document.body ? document.body.innerText : ''") or ""


def sign_in(c: Chrome, user: str, password: str, totp: str | None) -> str:
    """Return 'ok', 'totp', or a short reason. Leaves the browser signed in."""
    c.nav(SIGNIN, settle=4)
    # A browser K already signed into (through noVNC) lands on myaccount instead of
    # the identifier page. That is a success, not a missing field -- and it is the
    # path that never needs K's password to pass through this script.
    if not c.js("!!document.querySelector('input#identifierId, input[name=identifier], "
                "input[type=email]')"):
        here = c.js("location.href") or ""
        if "myaccount.google.com" in here or "mail.google.com" in here:
            return "ok"
        return "no-email-field"
    if not c.type_into("input#identifierId, input[name=identifier], input[type=email]",
                       user):
        return "no-email-field"
    c.click("#identifierNext")
    if not c.wait_js("!!document.querySelector('input[type=password]')", timeout=25):
        return "no-password-field"
    c.type_into("input[type=password]", password)
    c.click("#passwordNext")
    time.sleep(5)

    for _ in range(6):
        url = c.js("location.href") or ""
        text = page_text(c).lower()
        if "myaccount.google.com" in url or "mail.google.com" in url:
            return "ok"
        if any(k in text for k in ("2-step", "verification code", "tap yes",
                                   "check your phone", "get a verification code")):
            if not totp:
                return "totp"
            code_field = ("input[type=tel], input[name=totpPin], "
                          "input#totpPin, input[aria-label*='code' i]")
            if not c.type_into(code_field, totp):
                return "totp-no-field"
            c.click("#totpNext, button[type=submit], #idvPreregisteredPhoneNext")
            totp = None  # one attempt per code
            time.sleep(5)
            continue
        if "couldn't sign you in" in text or "couldn’t sign you in" in text:
            return "rejected-by-google"
        if "wrong password" in text or "couldn't find your google account" in text:
            return "bad-credential"
        time.sleep(3)
    return "unfinished"


def create_app_password(c: Chrome, name: str) -> str | None:
    """Open the app-password page, name one, and read it back. None on failure."""
    c.nav(APPPW, settle=6)
    text = page_text(c).lower()
    if "sign in" in text and "app password" not in text and "app passwords" not in text:
        return None
    if "2-step verification" in text and "app password" not in text:
        return "NO_2SV"  # 2-step verification is off; app passwords do not exist yet

    # The page's markup is not fixed, so try the shapes it has used, in order, and
    # keep the HTML when none of them match -- guessing blind from here is slower
    # than reading the real page once.
    name_field = ("input[type=text], input[aria-label*='name' i], "
                  "input[aria-labelledby*='name' i]")
    if not c.type_into(name_field, name):
        _dump(c, "apppw-no-field")
        return None

    for sel in ("button[jsname='V67aGc']",
                "//button[.//span[contains(., 'Create')]]",
                "//button[contains(., 'Create')]",
                "button:not([disabled])"):
        if sel.startswith("//"):
            expr = ("(function(){var r=document.evaluate(" + repr(sel) +
                    ",document,null,9,null).singleNodeValue;"
                    "if(r){r.click();return true}return false})()")
            if c.js(expr):
                break
        elif c.click(sel):
            break
    time.sleep(2)

    if not c.wait_js(
            r"/([a-z]{4}\s+){3}[a-z]{4}/.test(document.body.innerText)", timeout=15):
        _dump(c, "apppw-no-password")
        return None
    found = c.js(r"(document.body.innerText.match(/([a-z]{4}\s+){3}[a-z]{4}/)||[''])[0]")
    return (found or "").replace(" ", "").strip() or None


def _dump(c: Chrome, tag: str) -> None:
    """Save the page so a failed selector can be fixed from evidence, not a guess."""
    try:
        path = os.path.join("/tmp", f"apppw-{tag}-{int(time.time())}.html")
        html = c.js("document.documentElement.outerHTML") or ""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"  page dumped to {path}", file=sys.stderr)
    except Exception:
        pass


def store_secret(pairs: list[tuple[str, str]]) -> bool:
    """Write IMAP_ACCOUNTS to the repository secret. Returns True on success."""
    payload = json.dumps([{"user": u, "app_password": p} for u, p in pairs])
    try:
        subprocess.run(["gh", "secret", "set", "IMAP_ACCOUNTS",
                        "--repo", "kongkeat938/ai-content-lab",
                        "--body", payload],
                       check=True, capture_output=True, text=True)
        return True
    except Exception as exc:  # noqa: BLE001 - report, do not raise a stack trace
        print(f"  store failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--user", default=os.environ.get("GMAIL_USER"))
    ap.add_argument("--password", default=os.environ.get("GMAIL_PASSWORD"))
    ap.add_argument("--totp", default=os.environ.get("GMAIL_TOTP"))
    ap.add_argument("--app-name", default="OpenHands Pod")
    ap.add_argument("--out", help="write the app password here (outside the repo)")
    ap.add_argument("--accounts-file",
                    help="JSON list of {user,password,totp?} to do in one run")
    ap.add_argument("--signed-in", action="store_true",
                    help="browser is already signed in (K did it via noVNC); skip login")
    ap.add_argument("--store", action="store_true",
                    help="write IMAP_ACCOUNTS to the repository secret")
    args = ap.parse_args()

    jobs: list[dict] = []
    if args.accounts_file:
        jobs = json.load(open(args.accounts_file, encoding="utf-8"))
    elif args.user:
        jobs = [{"user": args.user, "password": args.password or "",
                 "totp": args.totp}]
    elif not args.signed_in:
        ap.error("give --user, or --accounts-file, or --signed-in")

    c = Chrome(args.port)
    results: list[tuple[str, str]] = []
    if args.signed_in:
        # One already-signed-in session serves every account's app-password page, so
        # only the account name differs per job.
        for job in (jobs or [{"user": "session"}]):
            user = job.get("user", "session")
            print(f"[{user}] using the signed-in session")
            pw = create_app_password(c, args.app_name)
            if pw == "NO_2SV":
                print(f"[{user}] 2-step verification is OFF -- enable it, then retry")
                continue
            if not pw:
                print(f"[{user}] could not read the app password back")
                continue
            results.append((user, pw))
            print(f"[{user}] app password created ({len(pw)} chars)")
    else:
        for job in jobs:
            user = job["user"]
            print(f"[{user}] signing in")
            state = sign_in(c, user, job["password"], job.get("totp"))
            if state == "totp":
                print(f"[{user}] needs a 2FA code: re-run with GMAIL_TOTP=<code>")
                continue
            if state != "ok":
                print(f"[{user}] sign-in failed: {state}")
                continue
            print(f"[{user}] signed in; creating app password")
            pw = create_app_password(c, args.app_name)
            if pw == "NO_2SV":
                print(f"[{user}] 2-step verification is OFF -- enable it, then retry")
                continue
            if not pw:
                print(f"[{user}] could not read the app password back")
                continue
            results.append((user, pw))
            print(f"[{user}] app password created ({len(pw)} chars)")

    if not results:
        return 1
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump([{"user": u, "app_password": p} for u, p in results], fh)
        print(f"wrote {args.out}")
    if args.store:
        print("stored" if store_secret(results) else "store failed")
    if not args.out and not args.store:
        print("no --out and no --store: nothing saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
