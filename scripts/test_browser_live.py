#!/usr/bin/env python3
"""The live view must actually relay pixels and input -- and the guard must FAIL if not.

`browser_live.py` sits between a human's browser and Chromium's DevTools protocol:
frames come out of `Page.startScreencast`, clicks go back in as
`Input.dispatchMouseEvent`. If either leg is broken, the page looks dead and the owner
blames the pod. So this test stands up a FAKE CDP (no real Chromium) that answers the
same two methods, points the live view at it, and checks:

  1. a binary frame reaches the client (the out leg), and
  2. a click the client sends lands on the CDP as `Input.dispatchMouseEvent` with the
     SAME coordinates (the in leg) -- not dropped, not shifted.

Then it breaks the input leg on purpose and requires the check to FAIL, so a passing
run cannot be a coincidence.

    python3 scripts/test_browser_live.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import signal
import socket
import subprocess
import sys
import time

import aiohttp
from aiohttp import web

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "browser_live.py")

# 1x1 white JPEG -- a real JPEG so the client-side Image() would decode it too.
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")

MOUSE = []


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


async def fake_cdp(port: int, drop_input: bool) -> web.AppRunner:
    async def json_list(_):
        return web.json_response([{
            "type": "page", "id": "T1", "url": "about:blank",
            "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/T1"}])

    async def events(_):
        return web.json_response(MOUSE)

    async def devtools(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            m = json.loads(msg.data)
            if m.get("method") == "Page.startScreencast":
                await ws.send_json({"method": "Page.screencastFrame", "params": {
                    "data": base64.b64encode(TINY_JPEG).decode(),
                    "sessionId": 1,
                    "metadata": {"deviceWidth": 800, "deviceHeight": 600}}})
            elif m.get("method") == "Input.dispatchMouseEvent" and not drop_input:
                MOUSE.append(m["params"])
            if "id" in m:
                await ws.send_json({"id": m["id"], "result": {}})
        return ws

    app = web.Application()
    app.router.add_get("/json", json_list)
    app.router.add_get("/_events", events)
    app.router.add_get("/devtools/page/T1", devtools)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    return runner


def wait_port(port: int, timeout: float = 15) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.15)
    return False


async def run_case(drop_input: bool) -> tuple[bool, str]:
    """Returns (relay_ok, detail). relay_ok is False when a leg is broken."""
    del MOUSE[:]
    cdp_port, view_port = free_port(), free_port()
    runner = await fake_cdp(cdp_port, drop_input)
    env = dict(os.environ, LIVE_CDP=f"http://127.0.0.1:{cdp_port}")
    proc = subprocess.Popen([sys.executable, BIN, "--port", str(view_port)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_port(view_port):
            return False, "live view did not start"
        got_frame = False
        got_click = False
        async with aiohttp.ClientSession() as s:
            ws = await s.ws_connect(f"http://127.0.0.1:{view_port}/ws")
            # out leg: expect a binary frame within a few seconds (meta JSON comes first)
            try:
                for _ in range(5):
                    msg = await asyncio.wait_for(ws.receive(), timeout=8)
                    if msg.type == aiohttp.WSMsgType.BINARY and msg.data:
                        got_frame = True
                        break
            except asyncio.TimeoutError:
                pass
            # in leg: send a click, then read it back from the fake CDP
            await ws.send_str(json.dumps({"t": "m", "a": "down", "x": 321, "y": 123, "b": 0}))
            await ws.send_str(json.dumps({"t": "m", "a": "up", "x": 321, "y": 123, "b": 0}))
            for _ in range(40):
                await asyncio.sleep(0.1)
                async with s.get(f"http://127.0.0.1:{cdp_port}/_events") as r:
                    evs = await r.json()
                if any(e.get("x") == 321 and e.get("y") == 123
                       for e in evs if e.get("type") == "mousePressed"):
                    got_click = True
                    break
            await ws.close()
        if not got_frame:
            return False, "no frame reached the client (out leg broken)"
        if not got_click:
            return False, "click did not reach CDP at the same coordinates (in leg broken)"
        return True, "frame relayed + click landed at 321,123"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        await runner.cleanup()


def main() -> int:
    fails = []

    print("healthy relay: a frame is sent and a click lands at the same coordinates")
    ok, detail = asyncio.run(run_case(drop_input=False))
    print(f"  {'ok  ' if ok else 'FAIL'} {detail}")
    if not ok:
        fails.append("healthy relay")

    print("broken input leg: the guard can FAIL (a dropped click must be reported)")
    ok, detail = asyncio.run(run_case(drop_input=True))
    print(f"  {'ok  ' if not ok else 'FAIL'} {detail}")
    if ok:
        fails.append("broken input leg not detected")

    print()
    if fails:
        print(f"FAILED: {len(fails)}: {', '.join(fails)}")
        return 1
    print("OK: the live view relays frames and input, and the guard can fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
