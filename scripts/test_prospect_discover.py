#!/usr/bin/env python3
"""The discovery ledger must refuse evidence it does not have.

Four things are load-bearing and each one is driven here:
  * a row with no URL is not a prospect,
  * the same URL twice is one prospect,
  * a 404 is not an opportunity,
  * robots.txt Disallow stops a source instead of being ignored.

The HTTP cases run against a local server, so the real code path is exercised
without touching a public site.
"""
from __future__ import annotations

import http.server
import importlib
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prospect_discover as pd  # noqa: E402

FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"User-agent: *\nDisallow: /private\n")
            return
        if self.path.startswith("/private"):
            self.send_response(200); self.end_headers(); self.wfile.write(b"<html>video editing</html>")
            return
        if self.path.startswith("/gone"):
            self.send_response(404); self.end_headers(); self.wfile.write(b"not found")
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<html>video editing reel</html>")


def main() -> int:
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    tmp = tempfile.mkdtemp()
    os.environ["PROSPECT_STORE"] = os.path.join(tmp, "store.json")
    importlib.reload(pd)

    print("classify")
    ok, _, why = pd.classify({"url": "", "title": "video editing", "text": ""})
    check("no URL is rejected", not ok and "no evidence URL" in why, why)
    ok, terms, why = pd.classify({"url": base + "/a", "title": "Edit my YouTube clips into shorts",
                                  "text": ""})
    check("a real request is kept", ok and terms, why)
    ok, _, why = pd.classify({"url": base + "/b", "title": "Build me a website", "text": ""})
    check("an unrelated headline is rejected", not ok, why)

    print("merge")
    pd.SOURCES = {"fake": (base + "/list", lambda: [
        {"source": "fake", "url": base + "/p/1", "title": "Video editing for reels", "text": "",
         "budget_text": "$50", "deadline_text": "", "contact_public": "", "posted_at": ""},
        {"source": "fake", "url": base + "/p/1?utm=x", "title": "Video editing for reels", "text": "",
         "budget_text": "$50", "deadline_text": "", "contact_public": "", "posted_at": ""},
    ])}
    pd.discover()
    db = pd.load()
    check("the same URL twice is one prospect", len(db["items"]) == 1, f"{len(db['items'])} stored")
    pd.discover()
    db = pd.load()
    check("a second run adds nothing", len(db["items"]) == 1, f"{len(db['items'])} stored")

    print("robots")
    pd.SOURCES = {"blocked": (base + "/private/list", lambda: [{"source": "blocked",
                                                                "url": base + "/private/x",
                                                                "title": "video editing",
                                                                "text": "", "budget_text": "",
                                                                "deadline_text": "",
                                                                "contact_public": "",
                                                                "posted_at": ""}])}
    pd.discover()
    db = pd.load()
    entry = db["sources"][0]
    check("robots Disallow stops the source", entry["error"] == "blocked by robots.txt", entry["error"])
    check("nothing from a blocked source is stored", len(db["items"]) == 1, f"{len(db['items'])}")

    print("expiry")
    db = pd.load()
    db["items"][0]["url"] = base + "/gone/1"
    db["items"].append({"id": "x2", "source": "fake", "url": base + "/ok/2",
                        "title": "Video editing for shorts", "text": "", "budget_text": "",
                        "deadline_text": "", "contact_public": "", "posted_at": "",
                        "status": "open", "kind": "prospect", "found_at": "t",
                        "last_checked_at": "t", "matched_terms": [], "match_reason": ""})
    pd.save(db)
    pd.check()
    db = pd.load()
    gone = [i for i in db["items"] if "/gone/" in i["url"]][0]
    live = [i for i in db["items"] if "/ok/" in i["url"]][0]
    check("a 404 becomes expired", gone["status"] == "expired", gone["status"])
    check("a live URL stays open", live["status"] == "open", live["status"])
    open_now = [i for i in db["items"] if i.get("status") == "open"]
    check("an expired row is not counted as an opportunity", len(open_now) == 1, f"{len(open_now)}")

    srv.shutdown()
    print("\nPASS test_prospect_discover" if not FAILED else f"\nFAIL test_prospect_discover: {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
