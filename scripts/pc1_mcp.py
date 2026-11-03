#!/usr/bin/env python3
"""Drive the PC1 winremote MCP server over raw HTTP.

Why this exists: the pc1-winremote_* tools are registered per conversation, so a
server restart makes them vanish from the tool list mid-session ("Unknown tool")
until a new conversation is started. The MCP server itself is still up, so talking
to it directly keeps PC1 drivable.

    python3 scripts/pc1_mcp.py list
    python3 scripts/pc1_mcp.py call Snapshot '{"max_width": 1280}'
    python3 scripts/pc1_mcp.py call Shell '{"command": "Get-Date"}'

Needs PC1_MCP_TOKEN and PC1_MCP_URL. The URL is the Tailscale funnel the
desktop agent publishes; it is deliberately not committed, because this
repository is public. It is visible in the conversation events where the MCP
server was registered.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("PC1_MCP_URL", "")


def _post(payload: dict, session: str | None, token: str) -> tuple[dict | None, str | None]:
    if not URL:
        raise SystemExit("PC1_MCP_URL is not set")
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "Authorization": f"Bearer {token}"}
    if session:
        headers["mcp-session-id"] = session
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as fh:
            body = fh.read().decode()
            sid = fh.headers.get("mcp-session-id", session)
    except urllib.error.HTTPError as exc:
        body, sid = exc.read().decode(), session
    for line in body.splitlines():
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    try:
        return json.loads(body), sid
    except json.JSONDecodeError:
        return None, sid


def open_session(token: str) -> str:
    r, sid = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {},
                               "clientInfo": {"name": "ak", "version": "1"}}}, None, token)
    if not sid:
        raise SystemExit(f"no session id; server said: {r}")
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid, token)
    return sid


def main() -> int:
    token = os.environ.get("PC1_MCP_TOKEN")
    if not token:
        raise SystemExit("PC1_MCP_TOKEN is not set")
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sid = open_session(token)
    if sys.argv[1] == "list":
        r, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid, token)
        for t in r["result"]["tools"]:
            print(f"{t['name']}: {t.get('description','')[:90]}")
        return 0
    if sys.argv[1] == "call":
        name = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        r, _ = _post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": name, "arguments": args}}, sid, token)
        if "error" in r:
            print(json.dumps(r["error"], ensure_ascii=False, indent=1))
            return 1
        for c in r["result"].get("content", []):
            print(c.get("text", ""))
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
