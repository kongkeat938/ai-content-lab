#!/usr/bin/env python3
"""The delivery pack must certify what it contains, and must FAIL when it cannot."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(ok: bool, label: str) -> None:
    global fails
    print(("  ok   " if ok else "  FAIL ") + label)
    if not ok:
        fails += 1


def main() -> int:
    if subprocess.run(["which", "ffmpeg"], capture_output=True,
                        stdin=subprocess.DEVNULL).returncode != 0:
        print("SKIP: no ffmpeg")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "clips")
        os.makedirs(src)
        for i in (1, 2):
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            f"testsrc=size=540x960:rate=10:duration=1", "-pix_fmt", "yuv420p",
                            os.path.join(src, f"clip_0{i}.mp4")], check=True,
                           stdin=subprocess.DEVNULL)
        out = os.path.join(tmp, "out")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "deliver.py"),
                            "--order", "o1", "--src", src, "--out", out],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        check(r.returncode == 0, f"deliver exits 0 ({r.stdout.strip().splitlines()[:1]})")
        zpath = os.path.join(out, "o1.zip")
        mpath = os.path.join(out, "o1.manifest.json")
        check(os.path.exists(zpath) and os.path.getsize(zpath) > 0, "the zip exists")
        m = json.load(open(mpath, encoding="utf-8"))
        check(len(m["files"]) == 2, "the manifest lists both clips")
        check(all(len(f["sha256"]) == 64 for f in m["files"]), "every file carries a sha256")
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
            check("manifest.json" in names, "the manifest travels inside the zip")
            ok = True
            for f in m["files"]:
                got = hashlib.sha256(z.read(f"clips/{f['name']}")).hexdigest()
                ok = ok and got == f["sha256"]
            check(ok, "the hashes read back identical from the zip")

        # a truncated clip must be refused, not packed
        bad = os.path.join(tmp, "bad")
        os.makedirs(bad)
        data = open(os.path.join(src, "clip_01.mp4"), "rb").read()
        open(os.path.join(bad, "broken.mp4"), "wb").write(data[:200])
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "deliver.py"),
                            "--order", "o2", "--src", bad, "--out", out],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        check(r.returncode != 0, "a truncated clip is REFUSED (exit != 0)")

        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "deliver.py"),
                            "--order", "o3", "--src", empty, "--out", out],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        check(r.returncode == 2, "an empty order is BLIND (exit 2)")
    print("FAIL" if fails else "PASS", "test_deliver")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
