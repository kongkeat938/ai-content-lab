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

IMAP credentials, when they exist, come from the environment:
    IMAP_HOST (default imap.gmail.com), IMAP_USER, IMAP_APP_PASSWORD
A Google account needs 2-step verification and an app password for this -- a normal
password will not work. Without them the script says so and still runs layer 1.
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

# slug -> (refresh-token env var, the account's address)
ACCOUNTS = {
    "dharma": ("YT_CH2_REFRESH_TOKEN", "farmmer.938@gmail.com"),
    "genx": ("YT_CH1_REFRESH_TOKEN", "kongkeat.938@gmail.com"),
    "aeris-music": ("YT_CH3_REFRESH_TOKEN", "aerismusic8@gmail.com"),
    "kongkeat-story": ("YT_CH4_REFRESH_TOKEN", "kongkeat.p3@gmail.com"),
}

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


def inbox_alerts(days: int) -> tuple[list[dict], str]:
    """Unread mail from the senders that matter. Returns (alerts, status note)."""
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    user = os.environ.get("IMAP_USER")
    pw = os.environ.get("IMAP_APP_PASSWORD")
    if not (user and pw):
        return [], ("no mail credential (IMAP_USER / IMAP_APP_PASSWORD unset) -- "
                    "the inbox cannot be read, so this layer is BLIND")
    alerts: list[dict] = []
    try:
        box = imaplib.IMAP4_SSL(host)
        box.login(user, pw)
        box.select("INBOX")
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        typ, data = box.search(None, f'(UNSEEN SINCE {since})')
        for num in (data[0].split() if data and data[0] else []):
            typ, raw = box.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            frm, subj = decode(msg.get("From", "")), decode(msg.get("Subject", ""))
            hay = f"{frm} {subj}".lower()
            if any(w in hay for w in ALERT_WORDS) or any(s in frm.lower() for s in IMPORTANT_SENDERS):
                alerts.append({"kind": "mail", "from": frm, "subject": subj,
                               "date": msg.get("Date", "")})
        box.logout()
        status = f"read {user}: {len(alerts)} flagged unread in {days} day(s)"
    except Exception as exc:  # noqa: BLE001 - any IMAP failure must be reported, not hidden
        return [], f"IMAP failed for {user}: {type(exc).__name__}: {exc}"
    return alerts, status


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
        for a in alerts:
            lines.append(f"- :email: **{a['from']}** — {a['subject']} ({a['date']})")
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
