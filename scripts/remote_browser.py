#!/usr/bin/env python3
"""Drive the headful Chromium that K signs into over noVNC.

K does not want to click through Google himself ("ak ต้องรีโมท มาทำให้ K"). The
password is the one thing only K can type -- Google refuses a program, and a password
in chat would land in the log. So the split is: K types the password once on the VNC
screen, ak drives the same browser over the DevTools protocol for everything after
(Brand-Account invite, OAuth consent, verification reads).

No dependency on a browser library: it talks to the CDP websocket directly.

    python3 scripts/remote_browser.py url                 # current url + title
    python3 scripts/remote_browser.py goto https://...    # navigate
    python3 scripts/remote_browser.py text                # visible text of the page
    python3 scripts/remote_browser.py click "Invite"      # click a button/link by text
    python3 scripts/remote_browser.py type "a@b.com"      # type into the focused field
    python3 scripts/remote_browser.py shot out.png        # screenshot (proof)
"""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.request

CDP = "http://127.0.0.1:9222"


def _ws():
    import websocket  # websocket-client
    tabs = json.load(urllib.request.urlopen(CDP + "/json"))
    pages = [t for t in tabs if t.get("type") == "page"]
    if not pages:
        raise SystemExit("no page open in the pod browser; run scripts/start_novnc.sh")
    return websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=30)


class CDP_:
    def __init__(self) -> None:
        self.ws = _ws()
        self.n = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                return m

    def js(self, expr: str):
        r = self.call("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")

    def close(self) -> None:
        self.ws.close()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    c = CDP_()
    try:
        if cmd == "url":
            print(c.js("document.title + ' | ' + location.href"))
        elif cmd == "goto":
            c.call("Page.navigate", {"url": args[0]})
            time.sleep(5)
            print(c.js("document.title + ' | ' + location.href"))
        elif cmd == "text":
            print((c.js("document.body ? document.body.innerText : ''") or "")[:4000])
        elif cmd == "click":
            label = args[0].replace('"', '\\"')
            hit = c.js(
                "(function(){var L=%r.toLowerCase();"
                # Google puts the real control inside a div id ending in 'Next'; the
                # visible span says 'Next' but clicking it alone does nothing.
                "var g=document.querySelector('[id$=Next] button,[id$=Next]');"
                "if(g&&L==='next'){g.click();return 'clicked '+(g.id||g.tagName);}"
                "var els=[...document.querySelectorAll("
                "'a,button,[role=button],span,div')];for(var e of els){var t=(e.innerText||"
                "e.textContent||'').trim().toLowerCase();if(t===L||t.includes(L)){e.click();"
                "return 'clicked: '+t.slice(0,60);}}return 'not found';})()" % label)
            print(hit)
        elif cmd == "type":
            val = args[0].replace('"', '\\"')
            print(c.js(
                "(function(){var e=document.activeElement;"
                "if(!e||!(e.tagName==='INPUT'||e.tagName==='TEXTAREA')){"
                "e=[...document.querySelectorAll('input[type=text],input[type=email],"
                "input:not([type]),textarea')].find(function(x){return x.offsetParent!==null;});}"
                "if(!e)return 'no field';e.focus();e.value=%r;"
                "e.dispatchEvent(new Event('input',{bubbles:true}));"
                "e.dispatchEvent(new Event('change',{bubbles:true}));"
                "return 'typed into '+(e.name||e.type||e.tagName);})()" % val))
        elif cmd == "shot":
            r = c.call("Page.captureScreenshot", {"format": "png"})
            data = base64.b64decode(r["result"]["data"])
            open(args[0], "wb").write(data)
            print(f"wrote {args[0]} ({len(data)} bytes)")
        else:
            print(f"unknown command {cmd!r}\n{__doc__}")
            return 2
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
