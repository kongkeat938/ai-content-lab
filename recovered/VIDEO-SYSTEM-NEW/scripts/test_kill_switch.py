#!/usr/bin/env python3
"""Every rail that builds or uploads must honour content/STOP.

The guard sweeps scripts/ for the rails that can spend money, quota or K's
reputation -- a content generator, an uploader, the foreman -- and fails if any of
them does not call kill_switch.require_running() from main(). It must be able to
go red: the set of rails is discovered from the source, never hardcoded, so a new
rail is covered the day it appears (K's rule, 2026-11-11: never hardcode the set a
guard checks).

Measured 2026-11-20: the STOP file was honoured by watchdog.py and publish_shorts.py
only; four generators and publish_batch/remake_shorts/publish_motion ran right
through it, so "everything is stopped" was false.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

# A rail is any script whose name marks it as building or publishing work. The
# pattern is the contract, not a list, so a new rail is covered automatically.
RAIL_PATTERNS = ("gen_", "publish_", "make_", "remake_", "foreman")


def is_rail(path: str) -> bool:
    name = os.path.basename(path)
    if name.startswith("test_") or not name.endswith(".py"):
        return False
    return name.startswith(RAIL_PATTERNS)


def calls_kill_switch(path: str) -> bool:
    """True when main() calls kill_switch.require_running() before doing work."""
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "require_running"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "kill_switch"):
                    return True
    return False


def run(script: str, args: list[str], cwd: str) -> int:
    p = subprocess.run([PY, script] + args, cwd=cwd, capture_output=True, text=True,
                       timeout=180)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    failures: list[str] = []

    def check(ok: bool, what: str, detail: str = "") -> None:
        print(f"  {'ok  ' if ok else 'FAIL'} {what}" + (f"  [{detail}]" if detail else ""))
        if not ok:
            failures.append(what)

    rails = sorted(p for p in
                   (os.path.join(HERE, f) for f in os.listdir(HERE))
                   if is_rail(p))
    print(f"1. every rail in scripts/ honours the kill switch ({len(rails)} found)")
    check(len(rails) >= 10, "the sweep found the known rails", f"{len(rails)}")
    for path in rails:
        check(calls_kill_switch(path),
              f"{os.path.basename(path)} calls kill_switch.require_running() in main()")

    print("\n2. the gate really stops a run (a rail must exit 3, not 0)")
    stop = os.path.join(ROOT, "content", "STOP")
    had_stop = os.path.exists(stop)
    backup = None
    if had_stop:
        backup = open(stop, encoding="utf-8").read()
    os.makedirs(os.path.dirname(stop), exist_ok=True)
    open(stop, "w", encoding="utf-8").write("TEST: kill switch guard\n")
    try:
        for script, args in (("gen_night_scripts.py", ["--out", tempfile.mkdtemp()]),
                             ("publish_batch.py", []),
                             ("foreman.py", [])):
            rc, out = run(os.path.join(HERE, script), args, ROOT)
            check(rc == 3, f"{script} exits 3 while STOP is present", f"rc={rc}")
            check("STOP file present" in out, f"{script} says why it stopped")
    finally:
        os.remove(stop)

    print("\n3. with the switch off, a rail is not blocked by it")
    rc, out = run(os.path.join(HERE, "gen_night_scripts.py"), ["--help"], ROOT)
    check("STOP file present" not in out, "no STOP complaint once the file is gone", f"rc={rc}")
    if had_stop and backup is not None:
        open(stop, "w", encoding="utf-8").write(backup)

    print("\n4. mutations must be caught")
    victim = os.path.join(HERE, "publish_batch.py")
    src = open(victim, encoding="utf-8").read()
    mutated = src.replace('    kill_switch.require_running("the uploader")\n', "")
    check(mutated != src, "M1 the gate line is where the guard looks for it")
    tmp = tempfile.mkdtemp()
    mpath = os.path.join(tmp, "publish_batch.py")
    open(mpath, "w", encoding="utf-8").write(mutated)
    check(not calls_kill_switch(mpath), "M1 a rail with the gate removed is reported as ungated")

    print("\n5. no workflow may disable the switch")
    wfdir = os.path.join(ROOT, ".github", "workflows")
    offenders = []
    for name in sorted(os.listdir(wfdir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        body = open(os.path.join(wfdir, name), encoding="utf-8").read()
        if kill_switch.STOP_ENV in body:
            offenders.append(name)
    check(not offenders, f"no workflow sets {kill_switch.STOP_ENV}", str(offenders))

    print()
    if failures:
        print(f"FAILED {len(failures)}:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS -- every build/publish rail stops on content/STOP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
