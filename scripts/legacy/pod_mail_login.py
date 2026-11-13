#!/usr/bin/env python3
"""Sign in to Google on the pod and create an app password, in one run.

This is the whole trip in one command, because the pod is short-lived: a reboot in
the middle of a manual sequence loses the browser session and the work has to start
again. Everything the flow needs is done here, in order.

    # password on the command line (it is not echoed into any file)
    python3 scripts/pod_mail_login.py --user kongkeat.938@gmail.com --password 'xxxx'

    # or read it from the repository secret, fetched and decrypted on the way in
    python3 scripts/pod_mail_login.py --user kongkeat.938@gmail.com --from-secret

    # after the phone prompt, add --store to write the new app password to the secret

Google will ask for a second factor. With "Tap Yes on your phone" the owner taps Yes
in the notification and then taps the number the screen shows; this script waits for
that and continues by itself. The app password is never printed to the log -- it goes
to the secret store, or to a file outside the repository with --out.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gmail_app_password as g  # noqa: E402

APPPW = "https://myaccount.google.com/apppasswords"
# Sign in with the app-password page as the destination: after the phone prompt the
# browser lands there directly. Navigating to it afterwards counts as a new sensitive
# action and makes Google ask for the second factor a second time.
SIGNIN = ("https://accounts.google.com/signin/v2/identifier"
          "?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
          "&continue=https%3A%2F%2Fmyaccount.google.com%2Fapppasswords")


def fetch_password(secret: str) -> str:
    """Decrypt a repository secret onto the pod, via scripts/fetch_secret.py."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_secret.py"), secret],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        sys.exit(f"could not fetch {secret}: {r.stderr.strip()[:300]}")
    return r.stdout


def signed_in(c: g.Chrome) -> bool:
    r = c.cmd("Storage.getCookies")
    names = {x["name"] for x in r.get("result", {}).get("cookies", [])}
    return "SID" in names


def do_login(c: g.Chrome, user: str, password: str, wait_s: int = 300) -> bool:
    c.nav(SIGNIN, settle=6)
    if signed_in(c):
        print("already signed in")
        return True
    if not c.type_into("input#identifierId, input[name=identifier], input[type=email]",
                       user):
        print("could not find the email field")
        return False
    c.real_click("#identifierNext")
    time.sleep(5)
    if not c.type_into("input[type=password]", password):
        print("could not find the password field")
        return False
    c.real_click("#passwordNext")
    time.sleep(8)

    if signed_in(c):
        print("signed in")
        return True

    text = (c.js("document.body.innerText") or "").lower()
    if "challenge" not in (c.js("location.href") or ""):
        print("sign-in did not reach a challenge:", text[:200].replace("\n", " / "))
        return False

    # Prefer the phone prompt: the owner taps once and the second tap is a number
    # already on screen, so nothing has to be typed or read back.
    print("second factor needed; choosing the phone prompt")
    c.real_click("", by_text="try another way")
    time.sleep(5)
    if c.real_click("", by_text="tap yes on your phone"):
        print("a notification was sent -- tap Yes, then tap the number shown")
    else:
        print("phone prompt unavailable; leave the code field for a typed code")

    deadline = time.time() + wait_s
    last = ""
    while time.time() < deadline:
        time.sleep(4)
        if signed_in(c):
            print("signed in after the second factor")
            return True
        url = c.js("location.href") or ""
        if "challenge" not in url:
            if signed_in(c):
                return True
            print("left the challenge without signing in:", url[:90])
            return False
        now = (c.js("document.body.innerText") or "")[:120].replace("\n", " / ")
        if now != last:
            last = now
            print("  ", now)
    print("timed out waiting for the second factor")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--password")
    ap.add_argument("--from-secret", action="store_true",
                    help="decrypt IMAP_ACCOUNTS from the repository secret and use it")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--app-name", default="OpenHands Pod")
    ap.add_argument("--out", help="write the app password here, outside the repo")
    ap.add_argument("--store", action="store_true",
                    help="write the new app password to IMAP_ACCOUNTS")
    ap.add_argument("--wait", type=int, default=300,
                    help="seconds to wait for the phone prompt")
    args = ap.parse_args()

    password = args.password
    if not password and args.from_secret:
        print("fetching the password from the repository secret...")
        password = fetch_password("IMAP_ACCOUNTS")
    if not password:
        ap.error("give --password, or --from-secret")

    c = g.Chrome(args.port)
    if not do_login(c, args.user, password, wait_s=args.wait):
        return 1

    print("opening the app-password page")
    # No navigation here: do_login leaves the browser on the page the owner just
    # approved, and re-opening it would ask for the second factor a third time.
    pw = g.create_app_password(c, args.app_name)
    if pw == "NO_2SV":
        print("2-step verification is off; turn it on, then run again")
        return 2
    if not pw:
        print("could not read an app password back")
        return 3
    print(f"app password created ({len(pw)} characters)")

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(pw)
        os.chmod(args.out, 0o600)
        print(f"written to {args.out}")
    if args.store:
        if g.store_secret([(args.user, pw)]):
            print("stored as IMAP_ACCOUNTS")
        else:
            print("could not store the secret")
            return 4
    if not args.out and not args.store:
        # Nothing else will show it, and Google shows an app password only once.
        print("APP_PASSWORD=" + pw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
