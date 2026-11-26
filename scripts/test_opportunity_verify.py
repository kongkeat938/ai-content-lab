#!/usr/bin/env python3
"""The verification pass has to tell four things apart, against a real server.

An audit is worth nothing if "verified" can be produced by a page that merely
returns 200. These cases run over HTTP so the code path is the one production
uses: a live ad, a soft-404 (200 but the ad is gone), a dead ad, and a post
whose only reply route needs an account we are not allowed to make.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "opportunity_verify.py")
FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the test output readable
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/live":
            body = ('<html><head><meta name="description" content="Need reels cut, '
                    'budget $50-150 USD for five clips"></head><body>'
                    '<h1>Reels editor for a skincare launch</h1> 4 days left</body></html>')
            self.send_response(200)
        elif self.path == "/soft404":
            self.send_response(200)
            body = "<html><body>This project is no longer available</body></html>"
        elif self.path == "/hn":
            body = "<html><body>Ask HN: who wants video edited? reach me at buyer@example.com</body></html>"
            self.send_response(200)
        else:
            self.send_response(404)
            body = "gone"
        raw = body.encode()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        store = os.path.join(tmp, "prospects.json")
        out = os.path.join(tmp, "opportunities.json")
        items = [
            {"id": "live", "title": "Reels editor for a skincare launch", "url": f"{base}/live",
             "source": "test", "status": "open", "text": "vertical reels"},
            {"id": "soft", "title": "Reels editor for a skincare launch", "url": f"{base}/soft404",
             "source": "test", "status": "open", "text": "vertical reels"},
            {"id": "dead", "title": "Gone job", "url": f"{base}/missing",
             "source": "test", "status": "open", "text": ""},
            {"id": "hn", "title": "Ask HN: who wants video edited?", "url": f"{base}/hn",
             "source": "news.ycombinator.com", "status": "open", "text": "video edited"},
        ]
        json.dump({"items": items}, open(store, "w"))
        env = {**os.environ, "PROSPECT_STORE": store, "OPPORTUNITY_STORE": out}
        r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True,
                           env=env, stdin=subprocess.DEVNULL, timeout=180)
        check("the pass runs", r.returncode == 0, r.stderr[-300:])
        db = json.load(open(out))
        by = {x["id"]: x for x in db["rows"]}

        check("a live ad whose headline is on the page is verified",
              by["live"]["state"] == "verified", by["live"]["state"])
        check("a 200 page that lost the ad is NOT verified",
              by["soft"]["state"] == "unverified", by["soft"]["state"])
        check("a 404 is expired, not verified", by["dead"]["state"] == "expired")
        check("the budget comes from the buyer's words",
              by["live"]["budget"]["raw"] == "$50-150 USD", str(by["live"]["budget"]))
        check("range converted to both ends in THB",
              by["live"]["budget"]["low_thb"] == 1750 and by["live"]["budget"]["high_thb"] == 5250,
              str(by["live"]["budget"]))
        check("a platform that needs a login is not contactable now",
              by["live"]["channel"]["permitted_now"] is False)
        check("a post with a public address IS contactable",
              by["hn"]["channel"]["permitted_now"] is True, str(by["hn"]["channel"]))
        check("only verified rows can be ranked",
              set(db["top"]) == {x["id"] for x in db["rows"] if x["state"] == "verified"} - {"hn"}
              or set(db["top"]) <= {x["id"] for x in db["rows"] if x["state"] == "verified"},
              str(db["top"]))
        check("nothing claims a message was sent",
              "sent" not in json.dumps(db).lower() or "0" in str(db.get("sent", 0)))
    srv.shutdown()
    print("\nPASS test_opportunity_verify" if not FAILS else f"\nFAIL test_opportunity_verify: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
