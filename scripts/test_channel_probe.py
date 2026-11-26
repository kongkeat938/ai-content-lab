#!/usr/bin/env python3
"""A channel counts only when a reader can see the address and robots allows it.

The three ways this measurement can lie, each reproduced here against a real
server: an address inside a tracking script, the site's own inbox, and a page
that is "contactable" only after a login. All three must come back as NOT a
channel.
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
SCRIPT = os.path.join(HERE, "channel_probe.py")
FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        raw = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path == "/robots.txt":
            return self._send(200, "User-agent: *\nDisallow: /blocked\n", "text/plain")
        if self.path == "/visible":
            return self._send(200, "<html><body>Need reels cut, mail me: buyer@studio.test"
                                   "<script>var t={adroll_email:'pixel@adroll.test'};"
                                   "var s='help@site.test';</script></body></html>")
        if self.path == "/login":
            return self._send(200, "<html><body>Video editor wanted. "
                                   "Please sign in to contact this client.</body></html>")
        if self.path == "/blocked":
            return self._send(200, "<html><body>mail: hidden@studio.test</body></html>")
        return self._send(404, "nope")


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "sources.json")
        out = os.path.join(tmp, "channels.json")
        json.dump({"sources": [
            {"name": "visible", "url": f"{base}/visible"},
            {"name": "login", "url": f"{base}/login"},
            {"name": "blocked", "url": f"{base}/blocked"},
        ]}, open(src, "w"))
        env = {**os.environ, "CHANNEL_STORE": out, "CHANNEL_SOURCES": src}
        r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL, timeout=180)
        check("the round runs", os.path.exists(out), r.stderr[-300:])
        db = json.load(open(out))
        by = {x["name"]: x for x in db["sources"]}
        check("a visible address is kept",
              by["visible"]["emails"] == ["buyer@studio.test"], str(by["visible"]["emails"]))
        check("an address inside a script is not a channel",
              "pixel@adroll.test" not in by["visible"]["emails"])
        check("the site's own inbox is not a channel",
              "help@site.test" not in by["visible"]["emails"])
        check("a login wall is recorded as a wall",
              by["login"]["state"] == "login_wall", by["login"]["state"])
        check("robots disallow wins over a visible address",
              by["blocked"]["state"] == "blocked_robots", by["blocked"]["state"])
        check("nothing was sent", "sent" not in json.dumps(db).lower())
    srv.shutdown()
    print("\nPASS test_channel_probe" if not FAILS else f"\nFAIL test_channel_probe: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
