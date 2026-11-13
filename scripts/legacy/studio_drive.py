#!/usr/bin/env python3
"""Drive a headful YouTube Studio tab over CDP (for the pod's noVNC browser).

Studio's SPA ignores a JS `element.click()` and a raw XTest warp+click; only a real
mouse event over the DevTools protocol works (measured 2026-11-13: it opened
การตั้งค่า -> สิทธิ์ -> the invite form). This wraps that into two primitives so a
session can navigate a Studio dialog without guessing coordinates.

    from studio_drive import Studio
    s = Studio()
    s.click_text("การตั้งค่า")            # opens the settings dialog
    s.click_text("สิทธิ์")               # the Permissions tab
    s.type_into("อีเมล", "a@example.com")  # the invite email box

`--shot OUT.png` saves a screenshot; `--url` prints the current URL. Read-only apart
from the clicks you ask for, and it never prints or stores a token.
"""
from __future__ import annotations

import argparse
import base64
import itertools
import json
import time
import urllib.request

CDP = "http://127.0.0.1:9222"


class Studio:
    def __init__(self, cdp: str = CDP):
        import websocket  # websocket-client
        tabs = [t for t in json.load(urllib.request.urlopen(cdp + "/json", timeout=8))
                if t.get("type") == "page"]
        if not tabs:
            raise RuntimeError("no page tab on CDP " + cdp)
        self.ws = websocket.create_connection(tabs[0]["webSocketDebuggerUrl"], timeout=30)
        self.ws.settimeout(30)
        self._ids = itertools.count(1)

    def call(self, method: str, params: dict | None = None) -> dict:
        i = next(self._ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == i:
                return msg

    def js(self, expr: str):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return r.get("result", {}).get("result", {}).get("value")

    def url(self) -> str:
        return self.js("location.href")

    def click_at(self, cx: float, cy: float) -> None:
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent",
                      {"type": t, "x": cx, "y": cy, "button": "left", "clickCount": 1})
            time.sleep(0.12)
        time.sleep(0.4)

    def rect_of(self, text: str, exact: bool = True):
        expr = (
            "(()=>{const q=%s;const els=[...document.querySelectorAll("
            "'a,button,ytcp-ve,tp-yt-paper-item,ytcp-navigation-item,ytcp-button,"
            "ytcp-icon-button,yt-formatted-string,input,textarea,div,span')];"
            "for(const el of els){const tx=(el.textContent||'').trim();"
            "if(%s?tx===q:tx.includes(q)){const r=el.getBoundingClientRect();"
            "if(r.width>0&&r.height>0)return {x:r.x+r.width/2,y:r.y+r.height/2,"
            "tag:el.tagName};}}return null;})()"
        ) % (json.dumps(text), "true" if exact else "false")
        return self.js(expr)

    def click_text(self, text: str, exact: bool = True, wait: float = 2.0):
        r = self.rect_of(text, exact)
        if not r:
            return None
        self.click_at(r["x"], r["y"])
        time.sleep(wait)
        return r

    def type_into(self, placeholder: str, value: str) -> bool:
        box = self.js(
            "(()=>{for(const el of document.querySelectorAll('textarea,input')){"
            "if((el.placeholder||'').includes(%s)){const r=el.getBoundingClientRect();"
            "if(r.width>0)return {x:r.x+r.width/2,y:r.y+r.height/2};}}return null;})()"
            % json.dumps(placeholder))
        if not box:
            return False
        self.click_at(box["x"], box["y"])
        self.call("Input.insertText", {"text": value})
        time.sleep(0.6)
        return True

    def shot(self, path: str) -> str:
        d = self.call("Page.captureScreenshot", {"format": "png"})["result"]["data"]
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(d))
        return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="store_true", help="print the current URL")
    ap.add_argument("--shot", metavar="OUT.png", help="save a screenshot")
    ap.add_argument("--click", metavar="TEXT", help="click the element with this text")
    ap.add_argument("--type", nargs=2, metavar=("PLACEHOLDER", "VALUE"),
                    help="type VALUE into the input whose placeholder contains PLACEHOLDER")
    a = ap.parse_args()
    s = Studio()
    if a.url:
        print(s.url())
    if a.click:
        print("clicked:", s.click_text(a.click))
    if a.type:
        print("typed:", s.type_into(a.type[0], a.type[1]))
    if a.shot:
        print("shot:", s.shot(a.shot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
