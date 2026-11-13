#!/usr/bin/env python3
"""Sign the pod's browser into a channel's OWNER account, so ak can act as them.

Option B hands the team a Manager seat, but the invite must come from the channel's
OWN account, and the pod is short-lived: a reboot loses the browser session and the
trip starts over. This does the whole sign-in in one command -- email, password, and
the phone prompt -- and leaves the browser signed in, so ak can then invite a
Manager and complete the consent without K at the machine.

    python3 scripts/pod_account_login.py --list
    python3 scripts/pod_account_login.py --user farmmer.938@gmail.com --from-secret
    python3 scripts/pod_account_login.py --user kongkeat.p3@gmail.com --password 'xxxx'

The password comes from the repository secret OWNER_LOGIN_PASSWORDS -- a JSON map of
owner email -> password -- fetched and decrypted on the way in, so no password is
typed into a shell or written to a file. K uses one password for all the accounts, so
the map is the same value repeated; keeping it keyed by email lets one account be
rotated without touching the others.

Google still asks for a second factor. With "Tap Yes on your phone" the owner taps
Yes and then taps the number the screen shows; this waits for that (K does it on the
noVNC screen). Nothing here prints the password.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gmail_app_password as g  # noqa: E402

# AddSession is the flow that ADDS an account even when the browser is already
# signed in as someone else (SIGNIN just redirects to that account's myaccount).
CHOOSER = "https://accounts.google.com/AddSession"

SECRET = "OWNER_LOGIN_PASSWORDS"


def fetch_secret(name: str) -> str:
    """Pull a repository secret onto the pod, decrypted (see scripts/fetch_secret.py)."""
    r = subprocess.run(["python3", os.path.join(HERE, "fetch_secret.py"), name],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"fetch_secret {name} failed: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def password_for(user: str, args) -> str:
    if args.password:
        return args.password
    if not args.from_secret:
        sys.exit("need --password or --from-secret")
    raw = fetch_secret(SECRET)
    try:
        table = json.loads(raw)
    except ValueError:
        # A single shared password (not a map) is also accepted.
        return raw
    if user not in table:
        sys.exit(f"{user} is not in {SECRET}; add it (owner email -> password)")
    return table[user]


def emails_on_page(c: g.Chrome) -> list[str]:
    body = c.js("document.body.innerText") or ""
    return sorted(set(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", body)))


def accounts_state(c: g.Chrome) -> dict[str, bool]:
    """Accounts the chooser lists. NOTE: it also lists accounts that are signed out,
    and the marker is not reliably placed, so this is only a hint, not proof."""
    c.nav("https://accounts.google.com/AccountChooser", settle=6)
    return {m: True for m in emails_on_page(c)}


def active_email(c: g.Chrome) -> str:
    """The email the browser is signed in as. myaccount shows exactly that one.

    Navigating here mid-challenge would throw the challenge away, so this is only
    safe to call once the flow has finished.
    """
    c.nav("https://accounts.google.com/", settle=5)
    got = emails_on_page(c)
    return got[0] if got else ""


def challenge(c: g.Chrome) -> bool:
    return "challenge" in (c.js("location.href") or "")


def login(c: g.Chrome, user: str, password: str, totp: str | None,
          wait_s: int) -> bool:
    c.nav(CHOOSER, settle=7)
    if not c.js("!!document.querySelector('input#identifierId, input[name=identifier],"
                "input[type=email]')"):
        # Already signed in AS the target (AddSession redirected to its myaccount).
        if active_email(c).lower() == user.lower():
            print(f"already signed in as {user}")
            return True
        print("no email field on the add-account page; check the browser")
        return False
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

    if not challenge(c):
        got = active_email(c)
        if got.lower() == user.lower():
            print(f"signed in as {user}")
            return True
        text = (c.js("document.body.innerText") or "").lower()
        if "wrong password" in text or "couldn't find your google account" in text:
            print("bad credential:", text[:160].replace("\n", " / "))
        else:
            print(f"sign-in did not reach a challenge (active account {got or '?'})")
        return False

    if totp:
        field = ("input[type=tel], input[name=totpPin], input#totpPin,"
                 "input[aria-label*='code' i]")
        if c.type_into(field, totp):
            c.real_click("#totpNext, button[type=submit], #idvPreregisteredPhoneNext")
            time.sleep(6)
            if active_email(c).lower() == user.lower():
                print(f"signed in as {user} with the typed code")
                return True
        print("typed code did not clear the challenge")
        return False

    # Prefer the phone prompt: the owner taps once and the second tap is a number
    # already on screen, so nothing has to be typed or read back.
    print("second factor needed; choosing the phone prompt")
    c.real_click("", by_text="try another way")
    time.sleep(5)
    if c.real_click("", by_text="tap yes on your phone"):
        print(f"a notification was sent to {user} -- on noVNC tap Yes, then the number")
    else:
        print("phone prompt unavailable; a typed code (--totp) may be needed")

    deadline = time.time() + wait_s
    last = ""
    while time.time() < deadline:
        time.sleep(4)
        if not challenge(c):
            if active_email(c).lower() == user.lower():
                print(f"signed in as {user} after the second factor")
                return True
            print("left the challenge without signing in as", user)
            return False
        now = (c.js("document.body.innerText") or "")[:120].replace("\n", " / ")
        if now != last:
            last = now
            print("  ", now)
    print("timed out waiting for the second factor")
    return False


def list_accounts(c: g.Chrome) -> None:
    """Show every account this browser can reach, and whether it is really signed in."""
    state = accounts_state(c)
    active = active_email(c)
    if not state:
        print("no signed-in accounts detected (open noVNC and add one)")
        return
    print("accounts the chooser knows (a hint -- it also lists signed-out ones):")
    for m in sorted(state):
        tag = " *" if m == active else "  "
        print(f"{tag} {m}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--user", default=os.environ.get("OWNER_USER"))
    ap.add_argument("--password", default=os.environ.get("OWNER_PASSWORD"))
    ap.add_argument("--from-secret", action="store_true",
                    help=f"read the password from the {SECRET} repository secret")
    ap.add_argument("--totp", default=os.environ.get("OWNER_TOTP"))
    ap.add_argument("--wait", type=int, default=300,
                    help="seconds to wait for the phone prompt")
    ap.add_argument("--list", action="store_true", help="show signed-in accounts and stop")
    args = ap.parse_args()

    c = g.Chrome(args.port)
    if args.list:
        list_accounts(c)
        return 0
    if not args.user:
        sys.exit("need --user (or --list)")
    pw = password_for(args.user, args)
    ok = login(c, args.user, pw, args.totp, args.wait)
    print("RESULT:", "OK" if ok else "FAILED", args.user)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
