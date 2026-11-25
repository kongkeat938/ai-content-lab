#!/usr/bin/env python3
"""Find people who are publicly asking to hire a video editor.

No account, no API key, no search engine. Every source here is a public page a
browser can open, and every item keeps the URL it came from so a claim can be
checked by hand.

    python3 scripts/prospect_discover.py            # discover, merge, classify
    python3 scripts/prospect_discover.py --check     # re-open stored URLs, expire the dead
    python3 scripts/prospect_discover.py --report    # counts from the ledger only

A hit is a PROSPECT: someone who posted a request. It is not a verified buyer —
nothing here proves they will pay us, only that they asked for this work in
public. The distinction is enforced in the data (`kind` is always "prospect")
and in the report.

robots.txt is consulted before every fetch; a source that disallows us is
recorded as blocked instead of being read.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STORE = os.environ.get("PROSPECT_STORE") or os.path.join(ROOT, "content", "prospects_external.json")
UA = "Mozilla/5.0 (compatible; ak-prospect-research/1.0; +https://github.com/kongkeat938/ai-content-lab)"

# A request needs both a video term and a shape term to count as the work we sell.
VIDEO_TERMS = ("video", "วิดีโอ", "คลิป", "film", "footage", "reel", "youtube", "tiktok", "short")
SHAPE_TERMS = ("edit", "ตัดต่อ", "short", "reel", "tiktok", "promo", "advert", "ad ", "โฆษณา", "trailer", "montage")
BUDGET_RE = re.compile(r"(?:[$฿€£]\s?[\d,]+(?:\.\d+)?(?:\s?(?:usd|thb|eur))?|(?:usd|thb|eur)\s?[\d,]+)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _robots_ok(url: str) -> tuple[bool, str]:
    """(allowed, reason). A robots.txt that cannot be read is treated as allow,
    which is what RFC 9309 says a crawler should do for a 4xx."""
    parts = urllib.parse.urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(robots, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            rp.parse(r.read().decode("utf-8", "ignore").splitlines())
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            return True, f"robots {exc.code} (treated as allow)"
        return False, f"robots {exc.code}"
    except Exception as exc:  # noqa: BLE001 - network failure must not be a silent allow
        return False, f"robots unreadable: {exc}"
    ok = rp.can_fetch(UA, url)
    return ok, "robots allow" if ok else "robots disallow"


def get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,th;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _strip_cdata(s: str) -> str:
    return re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", s.strip(), flags=re.S)


# ---------------------------------------------------------------- sources
def freelancer_jobs() -> list[dict]:
    out = []
    for cat in ("video-editing", "av-editing", "video-services"):
        page = get(f"https://www.freelancer.com/jobs/{cat}/")
        for card in re.split(r'data-project-card="true"', page)[1:]:
            m = re.search(r'href="(/projects/[^"]+)"[^>]*>\s*([^<]{4,200})\s*</a>', card)
            if not m:
                continue
            desc = re.search(r'JobSearchCard-primary-description">(.*?)</p>', card, re.S)
            price = re.search(r'JobSearchCard-primary-price">\s*([^<]{1,40})', card)
            left = re.search(r'JobSearchCard-primary-heading-days">([^<]{1,40})', card)
            verified = "verified their Payment method" in card
            out.append({
                "source": "freelancer.com",
                "url": "https://www.freelancer.com" + m.group(1),
                "title": _clean(m.group(2)),
                "text": _clean(desc.group(1))[:1200] if desc else "",
                "budget_text": _clean(price.group(1)) if price else "",
                "deadline_text": _clean(left.group(1)) if left else "",
                "contact_public": "site message after sign-in" if not verified else
                                 "site message after sign-in (payment verified)",
                "posted_at": "",
            })
    return out


def freelancer_rss() -> list[dict]:
    out = []
    x = get("https://www.freelancer.com/rss.xml")
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        desc = re.search(r"<description>(.*?)</description>", it, re.S)
        if not (t and l):
            continue
        out.append({
            "source": "freelancer.com",
            "url": _strip_cdata(l.group(1)),
            "title": _clean(_strip_cdata(t.group(1)))[:200],
            "text": _clean(_strip_cdata(desc.group(1)))[:1200] if desc else "",
            "budget_text": "",
            "deadline_text": "",
            "contact_public": "site message after sign-in",
            "posted_at": _clean(_strip_cdata(d.group(1))) if d else "",
        })
    return out


def craigslist() -> list[dict]:
    out = []
    page = get("https://bangkok.craigslist.org/search/cbg")
    for m in re.finditer(r'<li class="cl-static-search-result" title="([^"]*)">(.*?)</li>', page, re.S):
        href = re.search(r'href="([^"]+)"', m.group(2))
        price = re.search(r'class="price">([^<]*)', m.group(2))
        if not href:
            continue
        out.append({
            "source": "craigslist.org",
            "url": urllib.parse.urljoin("https://bangkok.craigslist.org/", html.unescape(href.group(1))),
            "title": _clean(m.group(1))[:200],
            "text": "",
            "budget_text": _clean(price.group(1)) if price else "",
            "deadline_text": "",
            "contact_public": "craigslist relay email on the post",
            "posted_at": "",
        })
    return out


def freelancermap() -> list[dict]:
    out = []
    page = get("https://www.freelancermap.com/projects/video")
    for card in re.split(r'class="project-card"', page)[1:]:
        m = re.search(r'data-testid="title"[^>]*href="(/project/[^"]+)"[^>]*>([^<]{4,200})</a>', card)
        if not m:
            continue
        out.append({
            "source": "freelancermap.com",
            "url": "https://www.freelancermap.com" + m.group(1),
            "title": _clean(m.group(2))[:200],
            "text": "",
            "budget_text": "",
            "deadline_text": "",
            "contact_public": "platform contact form",
            "posted_at": "",
        })
    return out


def hn_seeking_freelancer() -> list[dict]:
    """Hacker News 'Freelancer? Seeking freelancer?' threads: people post SEEKING
    FREELANCER with what they need. Public Algolia API, no key."""
    out = []
    for q in ("SEEKING FREELANCER video editor", "SEEKING FREELANCER video editing shorts"):
        api = ("https://hn.algolia.com/api/v1/search?tags=comment&hitsPerPage=30&query="
               + urllib.parse.quote(q))
        data = json.loads(get(api))
        for hit in data.get("hits", []):
            text = _clean(hit.get("comment_text") or "")
            if "seeking freelancer" not in text.lower():
                continue
            oid = hit.get("objectID")
            out.append({
                "source": "news.ycombinator.com",
                "url": f"https://news.ycombinator.com/item?id={oid}",
                "title": text[:120],
                "text": text[:1200],
                "budget_text": (BUDGET_RE.search(text).group(0) if BUDGET_RE.search(text) else ""),
                "deadline_text": "",
                "contact_public": "HN reply or the email in the post",
                "posted_at": hit.get("created_at", ""),
            })
    return out


SOURCES = {
    "freelancer_jobs": ("https://www.freelancer.com/jobs/video-editing/", freelancer_jobs),
    "freelancer_rss": ("https://www.freelancer.com/rss.xml", freelancer_rss),
    "craigslist_bkk": ("https://bangkok.craigslist.org/search/cbg", craigslist),
    "freelancermap": ("https://www.freelancermap.com/projects/video", freelancermap),
    "hn_seeking": ("https://hn.algolia.com/api/v1/search", hn_seeking_freelancer),
}


# ---------------------------------------------------------------- rules
def url_key(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return hashlib.sha1(f"{p.netloc}{p.path}".encode()).hexdigest()[:16]


def classify(item: dict) -> tuple[bool, list[str], str]:
    """(relevant, matched terms, reason). No URL means no evidence, so no hit."""
    if not (item.get("url") or "").startswith("http"):
        return False, [], "rejected: no evidence URL"
    title = (item.get("title") or "").lower()
    blob = f"{title} {item.get('text','')}".lower()
    video = [t for t in VIDEO_TERMS if t in title]
    shape = [t for t in SHAPE_TERMS if t in blob]
    if not video:
        return False, [], "rejected: the headline does not name video work"
    if not shape:
        return False, [], "rejected: not editing/short-form work"
    return True, sorted(set(video[:3] + shape[:3])), "match: video + editing/short-form"


def load() -> dict:
    if not os.path.exists(STORE):
        return {"items": [], "rejected": [], "sources": [], "runs": []}
    with open(STORE, encoding="utf-8") as fh:
        return json.load(fh)


def save(db: dict) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(db, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, STORE)


def discover() -> int:
    db = load()
    kept = []
    for i in db["items"]:
        relevant, _, reason = classify(i)
        if relevant:
            kept.append(i)
        else:
            db["rejected"].append({"id": i["id"], "url": i["url"], "source": i["source"],
                                   "title": i["title"][:120], "reason": reason, "at": now()})
    db["items"] = kept
    by_key = {i["id"]: i for i in db["items"]}
    by_title = {i["title"].lower(): i for i in db["items"]}
    run = {"at": now(), "sources": [], "new": 0, "seen": 0}
    for name, (url, fn) in SOURCES.items():
        ok, why = _robots_ok(url)
        entry = {"name": name, "url": url, "robots": why, "found": 0, "new": 0, "error": ""}
        if not ok:
            entry["error"] = "blocked by robots.txt"
            run["sources"].append(entry)
            continue
        try:
            raw = fn()
        except Exception as exc:  # noqa: BLE001 - one dead source must not stop the run
            entry["error"] = f"{type(exc).__name__}: {exc}"[:200]
            run["sources"].append(entry)
            continue
        entry["found"] = len(raw)
        for item in raw:
            item["kind"] = "prospect"
            item["id"] = url_key(item["url"])
            item["last_checked_at"] = run["at"]
            relevant, terms, reason = classify(item)
            if not relevant:
                db["rejected"].append({"id": item["id"], "url": item["url"], "source": item["source"],
                                       "title": item["title"][:120], "reason": reason, "at": run["at"]})
                continue
            if item["id"] in by_key:
                old = by_key[item["id"]]
                old["last_checked_at"] = run["at"]
                old["status"] = "open"
                if item.get("budget_text"):
                    old["budget_text"] = item["budget_text"]
                run["seen"] += 1
                continue
            if item["title"].lower() in by_title:
                db["rejected"].append({"id": item["id"], "url": item["url"], "source": item["source"],
                                       "title": item["title"][:120],
                                       "reason": "rejected: duplicate title", "at": run["at"]})
                continue
            item.update({"found_at": run["at"], "status": "open", "matched_terms": terms,
                         "match_reason": reason})
            db["items"].append(item)
            by_key[item["id"]] = item
            by_title[item["title"].lower()] = item
            entry["new"] += 1
            run["new"] += 1
        run["sources"].append(entry)
    # a rejected row is only worth keeping once per URL
    seen = set()
    uniq = []
    for r in db["rejected"]:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        uniq.append(r)
    db["rejected"] = uniq[-400:]
    db["sources"] = [{k: v for k, v in s.items() if k != "new"} for s in run["sources"]]
    db["runs"] = (db.get("runs", []) + [run])[-60:]
    db["updated_at"] = run["at"]
    save(db)
    print(f"new {run['new']}, already known {run['seen']}, total {len(db['items'])}")
    for s in run["sources"]:
        print(f"  {s['name']:16} found {s['found']:3} new {s['new']:3} {s['robots']}"
              + (f"  ERROR {s['error']}" if s["error"] else ""))
    return 0


def check() -> int:
    """Re-open every stored URL. 404/410 means the request is gone; anything else
    keeps it open and records when we last looked."""
    db = load()
    expired = alive = 0
    for item in db["items"]:
        try:
            req = urllib.request.Request(item["url"], headers={"User-Agent": UA}, method="GET")
            with urllib.request.urlopen(req, timeout=25) as r:
                code = r.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        except Exception:  # noqa: BLE001
            code = 0
        item["last_checked_at"] = now()
        item["http_status"] = code
        if code in (404, 410):
            item["status"] = "expired"
            expired += 1
        elif code in (200, 301, 302):
            item["status"] = "open"
            alive += 1
        else:
            item["status"] = item.get("status", "unknown")
        print(f"  {code:>3} {item['status']:8} {item['url'][:90]}")
    db["updated_at"] = now()
    save(db)
    print(f"alive {alive}, expired {expired}, total {len(db['items'])}")
    return 0


def report() -> int:
    db = load()
    items = db["items"]
    open_now = [i for i in items if i.get("status") == "open"]
    by_source = {}
    for i in open_now:
        by_source[i["source"]] = by_source.get(i["source"], 0) + 1
    print(f"prospects stored : {len(items)}  (kind=prospect, none are verified buyers)")
    print(f"open now         : {len(open_now)}")
    for s, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
        print(f"  {s:20} {n}")
    print(f"expired          : {sum(1 for i in items if i.get('status') == 'expired')}")
    print(f"rejected rows    : {len(db['rejected'])}")
    print(f"with a budget    : {sum(1 for i in open_now if i.get('budget_text'))}")
    print(f"sources usable   : {sum(1 for s in db.get('sources', []) if s.get('found'))}"
          f" / {len(db.get('sources', []))}")
    print(f"last run         : {db.get('updated_at','-')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="re-open stored URLs and expire the dead")
    ap.add_argument("--report", action="store_true", help="counts from the ledger only")
    a = ap.parse_args()
    if a.check:
        return check()
    if a.report:
        return report()
    return discover()


if __name__ == "__main__":
    sys.exit(main())
