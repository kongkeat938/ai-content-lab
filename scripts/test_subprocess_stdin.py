#!/usr/bin/env python3
"""No subprocess may inherit stdin -- measured 2026-11-19.

A guard test froze forever at process state "TNl" (stopped, not hung). Root
cause: `subprocess.run([...])` inherits stdin, ffmpeg then reads the TTY, and a
child that reads a TTY it does not own is stopped by SIGTTIN -- which suspends
the whole process group. Measured: the identical ffmpeg command with
`< /dev/null` returns 0 in 0.3 s; without it the run was still stopped after 90 s.

Why this is a ratchet and not a wall: CI runs with stdin already closed, so the
trap cannot fire there -- but every rail is also run by hand from a terminal,
which is where it bites. 33 files still carry a bare call (visible debt, counted
below). A file may keep its debt only at the exact count recorded in
`docs/subprocess_stdin_baseline.json`; the count may fall, never rise, and a file
that is clean is reported so its entry can be dropped. New code cannot add one.

Detection is by AST, not by regex: a regex both misses the aliased spellings
(`import subprocess as sp; sp.run(...)`, `from subprocess import run as r`) and
counts a call written inside a comment or a docstring, which is not a call.

    python3 scripts/test_subprocess_stdin.py          # exit 0 = no new bare call
    python3 scripts/test_subprocess_stdin.py --write  # re-record the debt (after a fix)
"""
from __future__ import annotations

import ast
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASELINE = os.path.join(ROOT, "docs", "subprocess_stdin_baseline.json")

CALLS = {"run", "Popen", "call", "check_output", "check_call"}


def _spawners(tree: ast.AST) -> tuple[set[str], set[str]]:
    """(names bound to the subprocess module, names bound to one of its calls)."""
    mod, direct = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "subprocess":
                    mod.add(a.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for a in node.names:
                if a.name in CALLS:
                    direct.add(a.asname or a.name)
    return mod, direct


def bare_calls(path: str) -> list[int]:
    """Line numbers of subprocess calls in `path` that do not pass `stdin=`."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise SystemExit(f"{path}: cannot parse -- {exc}") from exc
    mod, direct = _spawners(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        hit = (isinstance(fn, ast.Attribute) and fn.attr in CALLS
               and isinstance(fn.value, ast.Name) and fn.value.id in mod)
        if not hit and isinstance(fn, ast.Name) and fn.id in direct:
            hit = True
        if hit and not any(k.arg == "stdin" for k in node.keywords):
            out.append(node.lineno)
    return sorted(out)


def sweep() -> dict[str, int]:
    """Every Python file that can run -- tests included. Measured 2026-11-22: the
    freeze that burned 300 s per run lived in a *test* helper, and test files were
    excluded from this sweep, so the guard could not see the one place it bit."""
    found: dict[str, int] = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True)):
        rel = os.path.relpath(path, ROOT)
        if rel.startswith((".git", ".openhands")) or "/." in rel:
            continue
        n = len(bare_calls(path))
        if n:
            found[rel] = n
    return found


def main() -> int:
    found = sweep()
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump(found, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"recorded {sum(found.values())} bare call(s) in {len(found)} file(s)")
        return 0

    try:
        with open(BASELINE, encoding="utf-8") as fh:
            debt = json.load(fh)
    except (OSError, ValueError):
        debt = {}

    fails: list[str] = []
    for name, n in sorted(found.items()):
        allowed = debt.get(name, 0)
        if n > allowed:
            fails.append(f"{name}: {n} bare call(s), baseline allows {allowed} "
                         f"-- close stdin on the new one")
    for name, allowed in sorted(debt.items()):
        if name not in found:
            print(f"  ok   {name}: debt cleared ({allowed} -> 0), drop it from the "
                  f"baseline with --write")

    print(f"bare calls: {sum(found.values())} in {len(found)} file(s) "
          f"(recorded debt: {sum(debt.values())})")
    if fails:
        for f in fails:
            print("  FAIL " + f)
        print(f"FAIL -- {len(fails)} file(s) grew a bare subprocess call")
        return 1
    print("PASS -- no file has more bare calls than its recorded debt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
