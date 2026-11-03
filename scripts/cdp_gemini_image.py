#!/usr/bin/env python3
"""Generate an image with the Gemini web app, driven over CDP.

Why this exists: the Gemini *API* free tier returns 429 limit:0 for every image
model, and Pollinations caps service-wide (both measured 2026-10-31). The only
working free image path is to drive the browser that is already signed in.
`scripts/start_novnc.sh` starts that browser; this script drives it.

Usage:
    python3 scripts/cdp_gemini_image.py "prompt text" out.png

It finds a Gemini tab on CDP :9222, types the prompt, submits, waits for a
generated image, and saves the full-resolution file via the page's own
"download full size" button. Nothing is uploaded anywhere.

Two measured traps this handles:
  * The image is NOT an <img src="blob:">. It lives in
    <generated-image><single-image><img src="lh3.googleusercontent.com/...">.
    A blob-only search never finds it.
  * Drawing it to a canvas and calling toDataURL() throws a tainted-canvas
    error (cross-origin). The reliable path is to click the page's
    download-generated-image button and read the file from the download dir.

Free tools only: chromium + CDP.
"""
import json
import os
import sys
import time
import urllib.request

from websocket import create_connection

CDP = "http://localhost:9222"
DOWNLOAD_DIR = "/tmp/gemini_downloads"

IMG_SELECTOR = ("response-container GENERATED-IMAGE img, "
                "response-container SINGLE-IMAGE img, response-container img")
DOWNLOAD_BUTTON = ("response-container DOWNLOAD-GENERATED-IMAGE-BUTTON button, "
                   'response-container button[aria-label*="ownload full"]')


def pages():
    return [t for t in json.load(urllib.request.urlopen(f"{CDP}/json"))
            if t.get("type") == "page"]


class Tab:
    def __init__(self, ws):
        self.ws = create_connection(ws, timeout=180, max_size=None)
        self._id = 0

    def cmd(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method,
                                 "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                return msg

    def ev(self, expr, await_promise=False):
        return self.cmd("Runtime.evaluate",
                        {"expression": expr, "returnByValue": True,
                         "awaitPromise": await_promise}
                        ).get("result", {}).get("result", {}).get("value")


def gemini_tab():
    for t in pages():
        if "gemini.google.com" in t["url"]:
            return t
    raise SystemExit("no gemini tab; run scripts/start_novnc.sh first")


def wait_for_image(tab, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(4)
        if tab.ev(f"document.querySelectorAll('{IMG_SELECTOR}').length"):
            return True
    return False


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    prompt, out = sys.argv[1], sys.argv[2]
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    tab = Tab(gemini_tab()["webSocketDebuggerUrl"])
    tab.cmd("Page.bringToFront")          # a background tab does not render
    tab.cmd("Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": DOWNLOAD_DIR})

    editor = "rich-textarea .ql-editor, div[contenteditable='true']"
    tab.ev(f'document.querySelector("{editor}").focus()')
    tab.cmd("Input.insertText", {"text": prompt})
    time.sleep(1)
    tab.ev(f'document.querySelector("{editor}").focus()')
    for kind in ("keyDown", "keyUp"):
        tab.cmd("Input.dispatchKeyEvent",
                {"type": kind, "key": "Enter", "code": "Enter",
                 "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})

    if not wait_for_image(tab):
        raise SystemExit("timed out waiting for the image")

    before = set(os.listdir(DOWNLOAD_DIR))
    clicked = tab.ev("""(()=>{
      const b=document.querySelector('%s');
      if(!b) return 'no button';
      b.click(); return 'clicked';
    })()""" % DOWNLOAD_BUTTON)
    if clicked != "clicked":
        raise SystemExit(f"image present but no download button ({clicked})")

    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(2)
        new = [f for f in os.listdir(DOWNLOAD_DIR) if f not in before]
        if new:
            with open(os.path.join(DOWNLOAD_DIR, new[0]), "rb") as fh:
                raw = fh.read()
            with open(out, "wb") as fh:
                fh.write(raw)
            print(f"saved {out} ({len(raw)} bytes) from {new[0]}")
            return 0
    raise SystemExit("download did not appear")


if __name__ == "__main__":
    sys.exit(main())
