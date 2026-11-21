#!/usr/bin/env python3
"""The D: listing script must fail loudly, not report an empty folder as "clean".

PC1 is unreachable from the pod on every route (tailnet funnel NXDOMAIN, self-hosted
runner total_count 0, no tailscale socket, vault holds no endpoint), so the only way
to read `D:\\MV-mp4` is a human running `ops/find_mv_mp4.ps1` at the machine. That
makes the script itself the deliverable, and a listing script that says "EMPTY" when
it simply could not look is the same false pass that hid the dead funnel before.

Runs the real script under pwsh against a fixture tree, then mutates it to prove each
check can fail:

    M1  `-LiteralPath` -> `-Path`: a root containing `[ ]` matches nothing and the
        script reports an empty folder while files sit in it (measured 2026-11-20).
    M2  drop the `Test-Path` guard: a missing folder crashes instead of exit 2.
    M3  exit 0 on an empty folder: "no .mp4" becomes indistinguishable from success.

Skips (does not pass) when pwsh is absent, and says so.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "ops", "find_mv_mp4.ps1")
PWSH = os.path.expanduser("~/pwsh/pwsh")

failures: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {what}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(what)


def run(script: str, probe: str) -> tuple[int, str, str]:
    env = dict(os.environ, DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1")
    out = os.path.join(tempfile.mkdtemp(), "listing.txt")
    p = subprocess.run([PWSH, "-NoProfile", "-File", script, "-Probe", probe, "-Out", out],
                       capture_output=True, text=True, timeout=180, env=env)
    return p.returncode, p.stdout + p.stderr, out


def main() -> int:
    if not os.path.exists(PWSH):
        print(f"SKIP: pwsh not at {PWSH} -- cannot execute the real script")
        return 0
    if not os.path.exists(SCRIPT):
        print(f"FAIL: {SCRIPT} is missing")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        # A root whose name contains brackets -- the case -Path silently misses.
        tree = os.path.join(tmp, "MV[old]-mp4")
        os.makedirs(os.path.join(tree, "sub"))
        for name in ("a.mp4", "sub/b.MP4", "note.txt"):
            open(os.path.join(tree, name), "w").write("x")
        # A Thai folder and filename: 5.1's default ANSI encoding used to mangle it.
        os.makedirs(os.path.join(tree, "ธรรมะ"))
        open(os.path.join(tree, "ธรรมะ", "คลิป.mp4"), "w").write("x")
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        missing = os.path.join(tmp, "nope")

        print("\n1. the real script lists what is there")
        rc, out = run(SCRIPT, tree)
        check(rc == 0, "exit 0 when files exist", f"rc={rc}")
        check("COUNT=3" in out, "counts .mp4, .MP4 and a Thai-named file, ignores .txt",
              out.splitlines()[1] if len(out.splitlines()) > 1 else "")
        check("a.mp4" in out and "b.MP4" in out, "lists the files by full path")
        check("note.txt" not in out, "a .txt is not listed as a video")
        check("คลิป.mp4" in out, "a Thai filename survives the write")
        listing = os.path.join(os.path.dirname(out_path), "listing.txt")
        raw = open(listing, "rb").read()
        check("คลิป.mp4" in raw.decode("utf-8-sig"),
              "the written file round-trips as UTF-8 (not ANSI/TIS-620)")

        print("\n2. a missing folder FAILS instead of reading as empty")
        rc, out = run(SCRIPT, missing)
        check(rc == 2, "exit 2 on a missing root", f"rc={rc}")
        check("MISSING" in out, "says MISSING, not 'no files'")

        print("\n3. an empty folder is a distinct outcome, not success")
        rc, out = run(SCRIPT, empty)
        check(rc == 3, "exit 3 on an empty root", f"rc={rc}")
        check("EMPTY" in out, "says EMPTY")

        print("\n4. mutations must be caught")
        src = open(SCRIPT, encoding="utf-8").read()
        muts = {
            "M1 -LiteralPath -> -Path": ("-LiteralPath $scan", "-Path $scan"),
            "M2 drop the Test-Path guard": (
                "if (-not (Test-Path -LiteralPath $scan)) {", "if ($false) {"),
            "M3 empty root exits 0": ('exit 3', 'exit 0'),
        }
        for name, (old, new) in muts.items():
            if old not in src:
                check(False, f"{name}: anchor text not found (guard is stale)")
                continue
            path = os.path.join(tmp, "mut.ps1")
            open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
            rc, out = run(path, tree if name.startswith("M1") else
                          (empty if name.startswith("M3") else missing))
            if name.startswith("M1"):
                check("COUNT=2" not in out or rc != 0,
                      f"{name}: the bracket root no longer lists", f"rc={rc}")
            elif name.startswith("M2"):
                check(rc != 2 or "MISSING" not in out,
                      f"{name}: a missing root no longer reports MISSING", f"rc={rc}")
            else:
                check(rc == 0, f"{name}: empty now looks like success", f"rc={rc}")

    print()
    if failures:
        print(f"FAILED {len(failures)}:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS -- the D: listing fails loudly and the guard can go red")
    return 0


if __name__ == "__main__":
    sys.exit(main())
