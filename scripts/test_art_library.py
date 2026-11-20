#!/usr/bin/env python3
"""Guards for pulling clip art back from the PC1 library.

The failure this is written against: the library is a *fixed* set of files, so a
naive picker would hand the same picture to many clips -- exactly the repeat the
owner forbade ("no two clips may share an image, ever"). A second failure is a
library that is unreachable silently returning a picture anyway (or crashing the
rail). Both are checked here against a real HTTP server, not a mock, because the
code under test is the URL fetch and the ledger write.

    python3 scripts/test_art_library.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_short as MS  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def serve(root: str) -> tuple[ThreadingHTTPServer, str]:
    handler = partial(_Handler, directory=root)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


class _Handler(SimpleHTTPRequestHandler):
    """Static files plus the same /index.json the PC1 server exposes."""

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.json"):
            items = [{"file": n, "bytes": os.path.getsize(os.path.join(self.directory, n))}
                     for n in sorted(os.listdir(self.directory))
                     if n.lower().endswith(".png")]
            body = json.dumps({"count": len(items), "items": items}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def log_message(self, *a):
        pass


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="artlib-")
    lib = os.path.join(tmp, "library")
    os.makedirs(lib)
    # Eight distinct "pieces". Content matters: the ledger is keyed on md5.
    for i in range(8):
        with open(os.path.join(lib, f"piece_{i:02d}.png"), "wb") as fh:
            fh.write(b"PNGDATA" + bytes([i]) * 400)
    srv, url = serve(lib)
    ledger = os.path.join(tmp, "art_ledger.json")

    try:
        print("1) a clip pulls one piece and records it in the ledger")
        d1 = os.path.join(tmp, "clip1")
        got = MS.library_art(d1, "clip1", url, ledger)
        check(bool(got) and os.path.exists(got), "clip1 got a picture")
        with open(ledger, encoding="utf-8") as fh:
            used = json.load(fh)["md5"]
        check(len(used) == 1, f"ledger holds 1 md5 (got {len(used)})")
        check("clip1" in used.values(), "the ledger names clip1 as the owner")

        print("2) a second clip never gets the same picture")
        seen = {os.path.basename(got)}
        for n in range(2, 6):
            d = os.path.join(tmp, f"clip{n}")
            p = MS.library_art(d, f"clip{n}", url, ledger)
            check(bool(p), f"clip{n} got a picture")
            if p:
                with open(p, "rb") as fh:
                    seen.add(fh.read())
        check(len(seen) == 5, f"5 clips -> 5 distinct pictures (got {len(seen)})")

        print("3) the ledger survives and refuses to hand out a taken piece")
        with open(ledger, encoding="utf-8") as fh:
            used = json.load(fh)["md5"]
        check(len(used) == 5, f"ledger holds 5 md5 (got {len(used)})")

        print("4) an exhausted library falls back instead of repeating")
        for n in range(6, 10):
            MS.library_art(os.path.join(tmp, f"clip{n}"), f"clip{n}", url, ledger)
        p = MS.library_art(os.path.join(tmp, "clipX"), "clipX", url, ledger)
        check(p is None, "9th+ clip returns None so the caller generates a fresh one")

        print("5) an unreachable library returns None, it does not crash")
        dead = "http://127.0.0.1:9/none"
        check(MS.library_art(os.path.join(tmp, "clipD"), "clipD", dead, ledger) is None,
              "dead link -> None (the rail falls back to generating)")

        print("6) a rebuild of the same clip reuses the picture it already has")
        again = MS.library_art(d1, "clip1", url, ledger)
        check(again == got, "cached art.jpg is returned unchanged")
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    # 7) The one-shot index command is a GATE. Measured 2026-11-19 (Gemini
    # review): a failed fetch printed an error and then returned 0, so a caller
    # checking the exit code read a dead library as a clean refresh. A check that
    # only ever sees 0 cannot catch that, so this one demands a non-zero exit.
    dead_out = os.path.join(tempfile.mkdtemp(), "idx.json")
    r = subprocess.run([sys.executable, os.path.join(HERE, "art_library.py"),
                        "index", "--url", "http://127.0.0.1:9/none",
                        "--out", dead_out],
                       capture_output=True, text=True)
    check(r.returncode != 0,
          f"one-shot index on a dead library exits non-zero (got {r.returncode})")
    check(not os.path.exists(dead_out),
          "and writes no index file, so nothing reads a stale list as fresh")
    shutil.rmtree(os.path.dirname(dead_out), ignore_errors=True)

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed")
        return 1
    print("PASS: the PC1 library feeds clips without ever repeating a picture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
