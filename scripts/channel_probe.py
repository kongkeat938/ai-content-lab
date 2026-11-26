#!/usr/bin/env python3
"""One bounded round: which public sources let a provider reach a poster?

Phase 11 allows one round, at most 30 sources, and no account anywhere. So this
probe answers exactly three things per source, and refuses to guess:

  1. may we read it at all          -> robots.txt for that path
  2. can a poster be reached        -> a public address on the page, or a login wall
  3. is there video work on it      -> keyword hits in the listings we can read

A login wall is recorded as a wall, not as "no jobs". An address printed by the
poster is recorded as public; whether we may *use* a mailbox to reply is a
separate permission that this script does not grant itself.

    python3 scripts/channel_probe.py            # run the round
    python3 scripts/channel_probe.py --report   # summarise what was stored
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCES = os.environ.get("CHANNEL_SOURCES") or os.path.join(ROOT, "content", "channels_sources.json")
OUT = os.environ.get("CHANNEL_STORE") or os.path.join(ROOT, "content", "channels.json")
UA = "Mozilla/5.0 (compatible; ak-channel-research/1.0; +https://github.com/kongkeat938/ai-content-lab)"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LOGIN_RE = re.compile(r"(sign in to (contact|apply|view)|log ?in to (contact|apply|view)|"
                      r"เข้าสู่ระบบเพื่อ|ต้องเข้าสู่ระบบ|login required|please sign in)", re.I)
VIDEO_RE = re.compile(r"(video edit|video-editor|reel|short-form|tiktok|youtube|ตัดต่อ|剪辑|"
                      r"videographer|motion)", re.I)
JUNK = ("example.com", "sentry", "wixpress", "@2x", ".png", ".jpg", "noreply", "no-reply",
        "privacy@", "abuse@", "support@", "sentry.io", "adroll", "reporting.",
        "doubleclick", "cloudflare", "wix.com", "godaddy")
SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url: str, timeout: int = 25) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:  # noqa: BLE001 - unreachable is a result
        return 0, ""


def robots_allows(url: str) -> tuple[bool, str]:
    """RFC 9309: the longest matching rule wins; `*` and `$` are supported."""
    parts = urllib.parse.urlsplit(url)
    status, body = get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    if status != 200:
        return True, f"no robots.txt ({status}) -> allowed"
    rules, agents, applies = [], None, False
    for line in body.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            agents = val
            applies = val == "*" or val.lower() in UA.lower()
        elif applies and key in ("allow", "disallow"):
            rules.append((len(val), key == "allow", val))
    path = parts.path or "/"
    best = None
    for length, allow, pattern in rules:
        rx = "^" + re.escape(pattern).replace(r"\*", ".*")
        if pattern.endswith("$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path) and (best is None or length > best[0]):
            best = (length, allow)
    if best is None:
        return True, "no rule for this path"
    return best[1], f"{'allow' if best[1] else 'disallow'} rule for {path}"


def redact(addr: str) -> str:
    """Keep the evidence, drop the person: `someone@studio.test` -> `s***@studio.test`."""
    local, _, domain = addr.partition("@")
    return f"{local[:1]}***@{domain}"


def clean_emails(blob: str, site_host: str = "") -> list[str]:
    """Only addresses a reader can see, and never the site's own.

    Measured 2026-11-25: Workana, JobThai and We Work Remotely all "had" an
    address, and all three were telemetry (`reporting.workana.com`), the site's
    own sales inbox, and an AdRoll pixel. Counting those as contactable posters
    would have invented three channels that do not exist.
    """
    visible = SCRIPT_RE.sub(" ", blob or "")
    out = []
    for m in EMAIL_RE.finditer(visible):
        e = m.group(0).strip(".,;:()[]<>").lower()
        if any(j in e for j in JUNK) or e.endswith((".png", ".jpg", ".js", ".css")):
            continue
        if site_host and e.endswith("@" + site_host):
            continue
        r = redact(e)
        if r not in out:
            out.append(r)
    return out


def probe(src: dict) -> dict:
    url = src["url"]
    allowed, rule = robots_allows(url)
    row = {"name": src["name"], "url": url, "kind": src.get("kind", "html"),
           "checked_at": now(), "robots_allowed": allowed, "robots_rule": rule}
    if not allowed:
        row.update({"state": "blocked_robots", "http_status": None, "emails": [], "video_hits": 0})
        return row
    status, body = get(url)
    row["http_status"] = status
    if status != 200:
        row.update({"state": "unreachable" if status == 0 else f"http_{status}",
                    "emails": [], "video_hits": 0})
        return row
    site_host = re.sub(r"^www\.", "", urllib.parse.urlsplit(url).netloc)
    emails = clean_emails(body, site_host)
    wall = bool(LOGIN_RE.search(body))
    hits = len(VIDEO_RE.findall(body))
    row.update({"emails": emails[:5], "login_wall": wall, "video_hits": hits})
    if emails:
        row["state"] = "public_email"
    elif wall:
        row["state"] = "login_wall"
    else:
        row["state"] = "no_public_contact"
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        db = json.load(open(OUT, encoding="utf-8"))
        rows = db["sources"]
        print(f"sources checked        : {len(rows)}")
        for state in ("public_email", "login_wall", "no_public_contact",
                      "blocked_robots", "unreachable"):
            print(f"  {state:18} {sum(1 for r in rows if r['state'] == state)}")
        pub = [r for r in rows if r["state"] == "public_email"]
        print(f"with a public address  : {len(pub)}  -> {[r['name'] for r in pub]}")
        print(f"with video work visible: {sum(1 for r in rows if r['video_hits'] >= 3)}")
        print("sent                   : 0  (this program has no send path)")
        return 0

    srcs = json.load(open(SOURCES, encoding="utf-8"))["sources"]
    if len(srcs) > 30:
        print(f"refusing: {len(srcs)} sources > the 30 K allowed", file=sys.stderr)
        return 2
    rows = []
    for i, src in enumerate(srcs, 1):
        r = probe(src)
        rows.append(r)
        print(f"  [{i}/{len(srcs)}] {r['state']:18} {str(r.get('http_status')):>3} "
              f"emails={len(r['emails'])} video={r['video_hits']:>3}  {r['name'][:34]}")
    db = {"checked_at": now(), "count": len(rows), "sources": rows}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, OUT)
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
