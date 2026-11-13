#!/usr/bin/env python3
"""Serve the agent's Chromium tab as a live view a human can watch AND drive.

The pod already runs a headful Chromium with the DevTools protocol on :9222. That is
all a browser live view needs: `Page.startScreencast` streams JPEG frames of the tab,
and `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent` push a real gesture back in.
This serves that pair over one page, so the owner can sign in or clear a re-auth prompt
without a whole desktop being shipped to them.

Why not VNC: VNC encodes the entire X display (pixels of every window) and needs an
RFB stack (Xvfb + x11vnc + websockify). This sends only the tab, as JPEG, straight
from Chromium, and the click goes back through the same channel that already drives
the browser -- one process, no X client, no RFB.

    python3 scripts/browser_live.py                 # http://0.0.0.0:12000/
    python3 scripts/browser_live.py --port 12000
    python3 scripts/browser_live.py --target <id>   # pick a tab (default: first page)

Open the work-1 URL for port 12000. The view scales the tab to the window; a click maps
back to tab coordinates, so a click lands where it looks like it lands. Nothing here
reads or prints a credential; it only relays pixels and input.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request

import aiohttp
from aiohttp import web

CDP = os.environ.get("LIVE_CDP", "http://127.0.0.1:9222")

# Virtual key codes for the keys a sign-in form actually needs; printable characters
# go through Input.insertText instead, which is what a keyboard would produce anyway.
VK = {"Enter": 13, "Tab": 9, "Backspace": 8, "Escape": 27, " ": 32,
      "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40,
      "Home": 36, "End": 35, "Delete": 46}
SPECIAL = {"Enter": "Enter", "Tab": "Tab", "Backspace": "Backspace", "Escape": "Escape",
           " ": " ", "ArrowLeft": "ArrowLeft", "ArrowUp": "ArrowUp",
           "ArrowRight": "ArrowRight", "ArrowDown": "ArrowDown",
           "Home": "Home", "End": "End", "Delete": "Delete"}

PAGE = """<!doctype html><meta charset=utf-8><title>Browser Live View</title>
<style>
 body{margin:0;background:#111;color:#ddd;font:13px system-ui}
 #bar{padding:6px 10px;background:#1c1c1c;display:flex;gap:12px;align-items:center}
 #s{width:9px;height:9px;border-radius:50%;background:#a33;display:inline-block}
 #wrap{position:relative}
 canvas{display:block;width:100%;height:auto;background:#000;cursor:default;outline:none}
</style>
<div id=bar><span id=s></span><span id=st>connecting…</span>
 <span style="opacity:.6">click / type here to control the tab</span></div>
<div id=wrap><canvas id=c tabindex=0></canvas></div>
<script>
const c=document.getElementById('c'), x=c.getContext('2d');
const st=document.getElementById('st'), dot=document.getElementById('s');
let W=0,H=0, ws, iv;
function connect(){
 ws=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws');
 ws.binaryType='arraybuffer';
 ws.onopen=()=>{st.textContent='live';dot.style.background='#3c3';c.focus();};
 ws.onclose=()=>{st.textContent='reconnecting…';dot.style.background='#a33';setTimeout(connect,1200);};
 ws.onmessage=(e)=>{
   if(typeof e.data==='string'){const m=JSON.parse(e.data); if(m.w){W=m.w;H=m.h;} return;}
   const b=new Blob([e.data],{type:'image/jpeg'}); const u=URL.createObjectURL(b);
   const im=new Image(); im.onload=()=>{ if(c.width!==im.width||c.height!==im.height){c.width=im.width;c.height=im.height;} x.drawImage(im,0,0); URL.revokeObjectURL(u); };
   im.src=u;
 };
}
function pt(e){const r=c.getBoundingClientRect();
 return {x:Math.round((e.clientX-r.left)*(W/r.width)), y:Math.round((e.clientY-r.top)*(H/r.height))};}
function send(o){ if(ws&&ws.readyState===1) ws.send(JSON.stringify(o)); }
c.addEventListener('mousemove',e=>{const p=pt(e);send({t:'m',a:'move',x:p.x,y:p.y});});
c.addEventListener('mousedown',e=>{const p=pt(e);send({t:'m',a:'down',x:p.x,y:p.y,b:e.button});});
c.addEventListener('mouseup',e=>{const p=pt(e);send({t:'m',a:'up',x:p.x,y:p.y,b:e.button});});
c.addEventListener('contextmenu',e=>e.preventDefault());
c.addEventListener('wheel',e=>{e.preventDefault();const p=pt(e);send({t:'w',x:p.x,y:p.y,dx:e.deltaX,dy:e.deltaY});},{passive:false});
c.addEventListener('keydown',e=>{
  if(e.key==='Tab')e.preventDefault();
  const mod=(e.altKey?1:0)|(e.ctrlKey?2:0)|(e.metaKey?4:0)|(e.shiftKey?8:0);
  send({t:'k',down:true,key:e.key,mod});
});
c.addEventListener('keyup',e=>{const mod=(e.altKey?1:0)|(e.ctrlKey?2:0)|(e.metaKey?4:0)|(e.shiftKey?8:0);send({t:'k',down:false,key:e.key,mod});});
connect();
</script>"""


def page_target(want: str | None) -> dict:
    tabs = [t for t in json.load(urllib.request.urlopen(CDP + "/json", timeout=8))
            if t.get("type") == "page"]
    if not tabs:
        raise SystemExit("no page tab on CDP :9222")
    if want:
        for t in tabs:
            if t["id"] == want or want in t.get("url", ""):
                return t
    return tabs[0]


class Session:
    """One CDP websocket, with request/response correlation and an event queue."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse):
        self.ws = ws
        self._id = 0
        self._wait: dict[int, asyncio.Future] = {}
        self.events: asyncio.Queue = asyncio.Queue()
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            async for msg in self.ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                m = json.loads(msg.data)
                if "id" in m and m["id"] in self._wait:
                    self._wait.pop(m["id"]).set_result(m)
                elif "method" in m:
                    await self.events.put(m)
        except Exception:
            pass

    async def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        i = self._id
        fut = asyncio.get_event_loop().create_future()
        self._wait[i] = fut
        await self.ws.send_json({"id": i, "method": method, "params": params or {}})
        return await asyncio.wait_for(fut, timeout=30)

    async def close(self) -> None:
        self._reader.cancel()


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    target = page_target(request.app["target"])
    cdp = await aiohttp.ClientSession().ws_connect(
        target["webSocketDebuggerUrl"], max_msg_size=0, heartbeat=None)
    session = Session(cdp)
    await session.call("Page.enable")
    await session.call("Page.startScreencast",
                       {"format": "jpeg", "quality": 70, "maxWidth": 1600, "everyNthFrame": 1})

    ws = web.WebSocketResponse(max_msg_size=0, heartbeat=None)
    await ws.prepare(request)

    async def pump_frames() -> None:
        while not ws.closed:
            ev = await session.events.get()
            if ev.get("method") != "Page.screencastFrame":
                continue
            p = ev["params"]
            md = p.get("metadata", {})
            await ws.send_str(json.dumps({"w": md.get("deviceWidth"), "h": md.get("deviceHeight")}))
            await ws.send_bytes(__import__("base64").b64decode(p["data"]))
            await session.call("Page.screencastFrameAck", {"sessionId": p["sessionId"]})

    async def pump_input() -> None:
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                d = json.loads(msg.data)
            except ValueError:
                continue
            t = d.get("t")
            if t == "m":
                typ = {"move": "mouseMoved", "down": "mousePressed", "up": "mouseReleased"}.get(d.get("a"))
                if typ:
                    await session.call("Input.dispatchMouseEvent", {
                        "type": typ, "x": d["x"], "y": d["y"],
                        "button": "left" if d.get("b", 0) == 0 else "right",
                        "clickCount": 1 if typ != "mouseMoved" else 0})
            elif t == "w":
                await session.call("Input.dispatchMouseEvent", {
                    "type": "mouseWheel", "x": d["x"], "y": d["y"],
                    "deltaX": d.get("dx", 0), "deltaY": d.get("dy", 0)})
            elif t == "k":
                key = d.get("key", "")
                mod = d.get("mod", 0)
                if d.get("down") and len(key) == 1 and not (mod & 2) and not (mod & 4):
                    await session.call("Input.insertText", {"text": key})
                elif key in VK:
                    await session.call("Input.dispatchKeyEvent", {
                        "type": "keyDown" if d.get("down") else "keyUp",
                        "key": SPECIAL.get(key, key), "modifiers": mod,
                        "windowsVirtualKeyCode": VK[key], "nativeVirtualKeyCode": VK[key]})

    try:
        await asyncio.gather(pump_frames(), pump_input())
    except Exception:
        pass
    finally:
        try:
            await session.call("Page.stopScreencast")
        except Exception:
            pass
        await session.close()
        await cdp.close()
        await ws.close()
    return ws


async def index(_: web.Request) -> web.Response:
    return web.Response(text=PAGE, content_type="text/html")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=12000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--target", default=None, help="tab id or URL substring")
    a = ap.parse_args()
    app = web.Application()
    app["target"] = a.target
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    print(f"Browser Live View on http://{a.host}:{a.port}/  (CDP {CDP})", flush=True)
    web.run_app(app, host=a.host, port=a.port, print=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
