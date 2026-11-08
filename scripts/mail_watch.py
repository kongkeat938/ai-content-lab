#!/usr/bin/env python3
"""Watch the accounts for anything that could hurt the business, two ways.

K's point (2026-11-03): an unread mail can cost the business -- a copyright claim,
a monetisation decision, a payment problem -- and nobody would notice. So this
checks two layers:

  1. API-visible channel health (always available). A video that is rejected,
     region-restricted, or failed to process shows up in the Data API's `status`
     part. That is the same class of event YouTube also mails about, caught
     without any mail credential at all.

  2. The inbox itself (only if a mail credential is present). It signs in over
     IMAP and reports unread mail from the senders that matter: Google, YouTube,
     AdSense, and anything with a claim/strike/alert word. An inbox that cannot be
     read is reported as such -- silence must never look like "all clear".

    python3 scripts/mail_watch.py                 # both layers
    python3 scripts/mail_watch.py --api-only
    python3 scripts/mail_watch.py --imap-only --days 7

IMAP credentials, when they exist, come from the environment. One secret can hold
every account, so the password is entered once:
    IMAP_ACCOUNTS  -- JSON: [{"user": "...", "app_password": "..."}, ...]
    IMAP_USER / IMAP_APP_PASSWORD -- the older single-account pair, still accepted
    IMAP_HOST (default imap.gmail.com)
A Google account needs 2-step verification and an app password for this -- a normal
password will not work. The credential lives in a repository secret, never in a file
in this repository. Without it the script says so and still runs layer 1.
"""
from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.header import decode_header

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT = os.path.join(ROOT, "docs", "MAIL-ALERTS.md")
STATE = os.path.join(ROOT, "content", "mail_watch_state.json")
# Mail detail must not land in a public repository, so it goes outside it.
PRIVATE = os.environ.get("MAIL_WATCH_PRIVATE", os.path.expanduser("~/mail_watch_private.json"))

# slug -> (refresh-token env var, the account's address)
ACCOUNTS = {
    "dharma": ("YT_CH2_REFRESH_TOKEN", "farmmer.938@gmail.com"),
    "genx": ("YT_CH1_REFRESH_TOKEN", "kongkeat.938@gmail.com"),
    "aeris-music": ("YT_CH3_REFRESH_TOKEN", "aerismusic8@gmail.com"),
    "kongkeat-story": ("YT_CH4_REFRESH_TOKEN", "kongkeat.p3@gmail.com"),
}

# Channels that are no longer ak's to run. aeris-music was handed to another AI
# (K, 2026-11-03), so watching it is not a gap and not an alert -- it is simply
# out of scope. Keeping it here means the report cannot quietly drift back.
CANCELLED = {"aeris-music"}

# Mail from these is treated as business-critical even without a keyword.
IMPORTANT_SENDERS = ("youtube", "google", "adsense", "noreply", "no-reply",
                     "support", "copyright", "appeals")
# Words that mark a message as an alert regardless of sender.
ALERT_WORDS = ("claim", "strike", "copyright", "suspended", "suspend", "terminat",
               "monetiz", "demonetiz", "policy", "violat", "warning", "warning",
               "appeal", "restrict", "removed", "takedown", "payment", "tax",
               "verify", "verification", "required action", "action required",
               "ลิขสิทธิ์", "ระงับ", "คำเตือน", "นโยบาย", "ละเมิด", "ลบวิดีโอ",
               "สร้างรายได้", "ปลด", "ยืนยัน", "เรียกเก็บ", "จ่าย")


def load(rel: str, default):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def access_token(var: str) -> str | None:
    cid, sec, rt = os.environ.get("YT_CLIENT_ID"), os.environ.get("YT_CLIENT_SECRET"), os.environ.get(var)
    if not (cid and sec and rt):
        return None
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec,
                                   "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    try:
        return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30))["access_token"]
    except urllib.error.HTTPError as exc:
        print(f"  token refresh failed for {var}: {exc.code}", file=sys.stderr)
        return None


def api(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def channel_alerts(slug: str, token_var: str) -> list[dict]:
    """Problems the Data API can see: a rejected, failed or restricted video.

    These are exactly the events YouTube also mails about, so layer 1 covers the
    worst case even when no inbox can be read.
    """
    token = access_token(token_var)
    if not token:
        return [{"kind": "no-credential", "detail": f"{token_var} is not set"}]
    alerts: list[dict] = []
    try:
        ch = api("https://www.googleapis.com/youtube/v3/channels?part=contentDetails,statistics&mine=true", token)
        if not ch.get("items"):
            return [{"kind": "no-channel", "detail": "token has no channel"}]
        item = ch["items"][0]
        uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
        ids, page = [], None
        while True:
            u = (f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails"
                 f"&playlistId={uploads}&maxResults=50" + (f"&pageToken={page}" if page else ""))
            r = api(u, token)
            ids += [i["contentDetails"]["videoId"] for i in r["items"]]
            page = r.get("nextPageToken")
            if not page:
                break
        for i in range(0, len(ids), 50):
            v = api("https://www.googleapis.com/youtube/v3/videos?part=status,contentDetails&id="
                    + ",".join(ids[i:i + 50]), token)
            for it in v["items"]:
                st, cd = it["status"], it["contentDetails"]
                if st.get("rejectionReason"):
                    alerts.append({"kind": "rejected", "video": it["id"], "detail": st["rejectionReason"]})
                if st.get("failureReason"):
                    alerts.append({"kind": "failed", "video": it["id"], "detail": st["failureReason"]})
                if st.get("uploadStatus") not in ("processed",):
                    alerts.append({"kind": "not-processed", "video": it["id"], "detail": st.get("uploadStatus", "")})
                if cd.get("regionRestriction"):
                    alerts.append({"kind": "region-restricted", "video": it["id"], "detail": str(cd["regionRestriction"])})
        print(f"  {slug}: {len(ids)} videos checked, {len(alerts)} alert(s)")
    except urllib.error.HTTPError as exc:
        alerts.append({"kind": "api-error", "detail": f"{exc.code} {exc.read().decode()[:160]}"})
    return alerts


def decode(value: str) -> str:
    out = []
    for text, enc in decode_header(value or ""):
        out.append(text.decode(enc or "utf-8", "replace") if isinstance(text, bytes) else text)
    return "".join(out)


def mail_accounts() -> list[tuple[str, str, str]]:
    """(host, user, app_password) triples to read, from one secret.

    K holds one mailbox password that is used across accounts, and wants it stored
    once. The store is a repository *secret* (never a file in this public repo), and
    one secret can carry every account, so the password is entered a single time.

    Three shapes are accepted, so the easiest one can be used on a phone:

        one account per line, "user:app password"   <- easiest to type on mobile
        kongkeat.938@gmail.com:xxxx xxxx xxxx xxxx
        farmmer.938@gmail.com:xxxx xxxx xxxx xxxx

        a JSON list   [{"user": "...", "app_password": "..."}, ...]
        a JSON map    {"user": "app_password", ...}

    The older single pair, IMAP_USER + IMAP_APP_PASSWORD, still works and is merged
    in without duplicates. Google displays app passwords with spaces; the spaces are
    cosmetic and are stripped.
    """
    default_host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    pairs: list[tuple[str, str, str]] = []

    def add(host: str, user: str, pw: str) -> None:
        user, pw = (user or "").strip(), "".join((pw or "").split())
        if user and pw and not any(u == user for _h, u, _p in pairs):
            pairs.append((host or default_host, user, pw))

    raw = (os.environ.get("IMAP_ACCOUNTS") or "").strip()
    if raw:
        doc = None
        if raw[:1] in "[{":
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                doc = None
        if isinstance(doc, dict):
            doc = [{"user": u, "app_password": p} for u, p in doc.items()]
        if isinstance(doc, list):
            for item in doc:
                if isinstance(item, dict):
                    add(item.get("host") or default_host, item.get("user", ""),
                        item.get("app_password") or item.get("password") or "")
        else:
            # "user:password" per line. A line without a colon is ignored rather
            # than guessed at -- a mistyped credential must not read as a valid one.
            for line in raw.splitlines():
                line = line.strip().lstrip("-*").strip()
                if not line or ":" not in line:
                    continue
                user, pw = line.split(":", 1)
                add(default_host, user, pw)

    add(default_host, os.environ.get("IMAP_USER", ""),
        os.environ.get("IMAP_APP_PASSWORD", ""))
    return pairs



def inbox_alerts(days: int) -> tuple[list[dict], str]:
    """Unread mail from the senders that matter, across every configured account.

    Returns (alerts, status note). The note never contains a password, and the
    alerts never contain the account password either -- only sender and subject,
    which go to a private file outside the repo.
    """
    accounts = mail_accounts()
    if not accounts:
        return [], ("no mail credential (IMAP_ACCOUNTS, or IMAP_USER / "
                    "IMAP_APP_PASSWORD unset) -- the inbox cannot be read, so "
                    "this layer is BLIND")
    alerts: list[dict] = []
    notes: list[str] = []
    for host, user, pw in accounts:
        try:
            box = imaplib.IMAP4_SSL(host)
            box.login(user, pw)
            box.select("INBOX")
            since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
            typ, data = box.search(None, f'(UNSEEN SINCE {since})')
            found = 0
            for num in (data[0].split() if data and data[0] else []):
                typ, raw = box.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(raw[0][1])
                frm, subj = decode(msg.get("From", "")), decode(msg.get("Subject", ""))
                hay = f"{frm} {subj}".lower()
                if any(w in hay for w in ALERT_WORDS) or any(s in frm.lower() for s in IMPORTANT_SENDERS):
                    alerts.append({"kind": "mail", "account": user, "from": frm,
                                   "subject": subj, "date": msg.get("Date", "")})
                    found += 1
            box.logout()
            notes.append(f"read {user}: {found} flagged unread in {days} day(s)")
        except Exception as exc:  # noqa: BLE001 - any IMAP failure must be reported, not hidden
            notes.append(f"IMAP failed for {user}: {type(exc).__name__}: {exc}")
    return alerts, "; ".join(notes)



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-only", action="store_true")
    ap.add_argument("--imap-only", action="store_true")
    ap.add_argument("--days", type=int, default=3, help="how far back to read unread mail")
    ap.add_argument("--write", action="store_true", help="write docs/MAIL-ALERTS.md")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    lines = [f"# Account watch — {now.isoformat(timespec='minutes')}", ""]
    total = 0       # real business alerts
    gaps = 0        # something could not be checked (a missing credential, an API error)
    blind = False

    if not args.imap_only:
        lines.append("## Channel health (Data API — always available)")
        for slug, (var, _addr) in ACCOUNTS.items():
            if slug in CANCELLED:
                lines.append(f"- **{slug}**: out of scope (handed to another AI) — not watched")
                continue
            alerts = channel_alerts(slug, var)
            real = [a for a in alerts if a["kind"] not in ("no-credential", "api-error")]
            gap = [a for a in alerts if a["kind"] in ("no-credential", "api-error")]
            total += len(real)
            gaps += len(gap)
            if not alerts:
                lines.append(f"- **{slug}**: clean")
            for a in real:
                lines.append(f"- **{slug}**: :warning: {a['kind']} — {a.get('video','')} {a['detail']}")
            for a in gap:
                lines.append(f"- **{slug}**: cannot check — {a['detail']}")
        lines.append("")

    if not args.api_only:
        lines.append("## Inbox (IMAP — needs an app password)")
        alerts, status = inbox_alerts(args.days)
        lines.append(f"- {status}")
        if "cannot be read" in status or "IMAP failed" in status:
            blind = True
        total += len(alerts)
        # This report is committed to a public repository, so it records that an
        # alert arrived and how many -- never the sender or the subject line.
        # The detail goes to a private file outside the repo.
        for i, _a in enumerate(alerts, 1):
            lines.append(f"- :email: alert {i} — recorded privately, not printed here")

        if alerts:
            with open(PRIVATE, "w", encoding="utf-8") as fh:
                json.dump({"checked_at": now.isoformat(timespec="seconds"), "alerts": alerts},
                          fh, indent=2, ensure_ascii=False)
        lines.append("")

    report = "\n".join(lines) + "\n"
    print(report)
    if args.write:
        with open(REPORT, "w", encoding="utf-8") as fh:
            fh.write(report)
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump({"checked_at": now.isoformat(timespec="seconds"), "alerts": total,
                       "gaps": gaps, "inbox_blind": blind}, fh, indent=2)
            fh.write("\n")
        print(f"wrote {os.path.relpath(REPORT, ROOT)}")

    if total:
        return 1
    return 2 if blind else 0


if __name__ == "__main__":
    sys.exit(main())
