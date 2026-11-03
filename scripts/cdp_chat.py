#!/usr/bin/env python3
"""Ask the signed-in ChatGPT web app a question over CDP, print the answer.

Companion to scripts/cdp_gemini_image.py: some accounts are signed in on the
noVNC desktop (scripts/start_novnc.sh) but their APIs are not available, so the
browser is the only channel. This types a prompt into the ChatGPT tab on
CDP :9222, submits, waits for the answer to settle, and prints the reply text.

Usage:
    python3 scripts/cdp_chat.py "your question"

Free tools only: chromium + CDP.
"""
import json
import sys
import time
import urllib.request

from websocket import create_connection

CDP = "http://localhost:9222"


def pages():
    return [t for t in json.load(urllib.request.urlopen(f"{CDP}/json"))
            if t.get("type") == "page"]


class Tab:
    def __init__(self, ws):
        self.ws = create_connection(ws, timeout=300, max_size=None)
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


def chatgpt_tab():
    for t in pages():
        if "chatgpt.com" in t["url"]:
            return t
    raise SystemExit("no chatgpt tab; run scripts/start_novnc.sh and log in")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    prompt = sys.argv[1]

    tab = Tab(chatgpt_tab()["webSocketDebuggerUrl"])
    tab.cmd("Page.bringToFront")          # a background tab does not render

    editor = '#prompt-textarea, div[contenteditable="true"]'
    tab.ev(f'document.querySelector("{editor}").focus()')
    tab.cmd("Input.insertText", {"text": prompt})
    time.sleep(1)
    tab.ev(f'document.querySelector("{editor}").focus()')
    for kind in ("keyDown", "keyUp"):
        tab.cmd("Input.dispatchKeyEvent",
                {"type": kind, "key": "Enter", "code": "Enter",
                 "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})

    # wait until a new assistant turn appears and stops streaming
    time.sleep(5)
    prev = -1
    stable = 0
    deadline = time.time() + 240
    while time.time() < deadline:
        time.sleep(4)
        n = tab.ev("document.querySelectorAll('[data-message-author-role=\"assistant\"]').length") or 0
        if n == prev:
            stable += 1
        else:
            stable = 0
            prev = n
        streaming = tab.ev("""!!document.querySelector('button[data-testid="stop-button"], .result-streaming')""")
        if n and not streaming and stable >= 2:
            break
    text = tab.ev("""(()=>{const a=document.querySelectorAll('[data-message-author-role="assistant"]');
      return a.length?a[a.length-1].innerText:''})()""")
    print(text or "(no answer)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
