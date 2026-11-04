#!/usr/bin/env python3
"""A one-page upload inbox so K can send a voice recording to the pod.

K records on his phone. There is no microphone on PC1, no way to attach audio in
the chat, and the IMAP inbox cannot be read (no app password). What does work is
a browser: open this page, pick the file, it lands in `work/k_voice/inbox/`.

    python3 scripts/voice_inbox.py            # http://0.0.0.0:12001
    python3 scripts/voice_inbox.py --port 12001

Serves on the pod's work-2 host, so the URL is
https://work-2-zmmehfjlyrrhipvr.prod-runtime.all-hands.dev/

Uploads are size-capped and restricted to audio/zip extensions; the name is
sanitised so a crafted filename cannot escape the inbox directory. This is a
personal inbox on a private pod, not a public service.
"""
from __future__ import annotations

import argparse
import email.parser
import html
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INBOX = os.path.join(ROOT, "work", "k_voice", "inbox")

MAX_BYTES = 200 * 1024 * 1024          # a few minutes of phone audio, with room
ALLOWED = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".mp4",
           ".zip", ".webm", ".amr", ".3gp"}

PAGE = """<!doctype html><html lang="th"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ส่งไฟล์เสียงให้ ak</title>
<style>
 body{{font-family:system-ui,'Segoe UI',sans-serif;background:#0f1720;color:#e8eef5;
      margin:0;padding:24px;max-width:640px;margin:auto}}
 h1{{font-size:20px}} p{{color:#9fb0c0;line-height:1.6}}
 .drop{{border:2px dashed #2f4a63;border-radius:14px;padding:28px;text-align:center;
        background:#132030;margin:18px 0}}
 input[type=file]{{width:100%;margin:12px 0;color:#cfe}}
 button{{background:#1f6feb;color:#fff;border:0;border-radius:10px;padding:14px 22px;
         font-size:16px;width:100%}}
 .ok{{background:#12331f;border:1px solid #2ea043;border-radius:10px;padding:14px;
      margin:14px 0}}
 ul{{color:#9fb0c0;font-size:14px}} code{{color:#e8eef5}}
</style>
<h1>ส่งไฟล์เสียงให้ ak</h1>
<p>อัดเสียงด้วยมือถือ → เลือกไฟล์ด้านล่าง → กดส่ง ไฟล์จะเข้าเครื่อง ak ทันที</p>
{message}
<form class="drop" method="post" enctype="multipart/form-data">
  <input type="file" name="file" accept="audio/*,.zip" required>
  <button type="submit">ส่งไฟล์</button>
</form>
<p>ไฟล์ที่รับได้: mp3, wav, m4a, aac, ogg, opus, flac, mp4, zip (สูงสุด 200 MB)</p>
<p>ไฟล์ที่ส่งแล้ว:</p><ul>{listing}</ul>
"""


def _listing() -> str:
    if not os.path.isdir(INBOX):
        return "<li>ยังไม่มีไฟล์</li>"
    rows = []
    for name in sorted(os.listdir(INBOX), reverse=True)[:20]:
        path = os.path.join(INBOX, name)
        if os.path.isfile(path):
            kb = os.path.getsize(path) / 1024
            rows.append(f"<li>{html.escape(name)} — {kb:.0f} kB</li>")
    return "".join(rows) or "<li>ยังไม่มีไฟล์</li>"


def _safe_name(name: str) -> str:
    name = os.path.basename(name or "voice")
    name = re.sub(r"[^A-Za-z0-9._\-\u0E00-\u0E7F ]", "_", name).strip() or "voice"
    return name


def _parse_upload(ctype: str, body: bytes):
    """Return (filename, data) from a multipart/form-data body, or (None, None)."""
    head = f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    msg = email.parser.BytesParser().parsebytes(head + body)
    if not msg.is_multipart():
        return None, None
    for part in msg.walk():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "file":
            continue
        return part.get_filename(), part.get_payload(decode=True) or b""
    return None, None


class Handler(BaseHTTPRequestHandler):
    server_version = "voice-inbox/1.0"

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - stdlib naming
        body = PAGE.format(message="", listing=_listing()).encode()
        self._send(200, body)

    def do_POST(self):  # noqa: N802
        ctype = self.headers.get("Content-Type", "")
        if not ctype.startswith("multipart/form-data"):
            self._send(400, PAGE.format(
                message='<div class="ok">ต้องส่งเป็นฟอร์มไฟล์</div>',
                listing=_listing()).encode())
            return
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_BYTES + (1 << 20):
            self._send(413, PAGE.format(
                message='<div class="ok">ไฟล์ใหญ่เกิน 200 MB</div>',
                listing=_listing()).encode())
            return
        try:
            filename, data = _parse_upload(ctype, self.rfile.read(length))
        except Exception as exc:  # noqa: BLE001
            self._send(400, PAGE.format(
                message=f'<div class="ok">อ่านไฟล์ไม่ได้: {html.escape(str(exc))}</div>',
                listing=_listing()).encode())
            return

        if not filename:
            self._send(400, PAGE.format(
                message='<div class="ok">ยังไม่ได้เลือกไฟล์</div>',
                listing=_listing()).encode())
            return

        name = _safe_name(filename)
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED:
            self._send(400, PAGE.format(
                message=f'<div class="ok">นามสกุล {html.escape(ext)} ไม่รับ</div>',
                listing=_listing()).encode())
            return
        if not data:
            self._send(400, PAGE.format(
                message='<div class="ok">ไฟล์ว่าง</div>',
                listing=_listing()).encode())
            return

        os.makedirs(INBOX, exist_ok=True)
        dest = os.path.join(INBOX, name)
        i = 1
        while os.path.exists(dest):
            stem, e = os.path.splitext(name)
            dest = os.path.join(INBOX, f"{stem}_{i}{e}")
            i += 1
        with open(dest, "wb") as fh:
            fh.write(data)

        size_mb = len(data) / (1024 * 1024)
        print(f"received {dest} ({size_mb:.2f} MB)", file=sys.stderr)
        self._send(200, PAGE.format(
            message=(f'<div class="ok">รับแล้ว: {html.escape(os.path.basename(dest))} '
                     f'({size_mb:.1f} MB) — ak เห็นไฟล์แล้ว</div>'),
            listing=_listing()).encode())

    def log_message(self, fmt, *args):  # quieter than the default
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=12001)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    os.makedirs(INBOX, exist_ok=True)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"voice inbox on http://{args.host}:{args.port}  ->  {INBOX}")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
