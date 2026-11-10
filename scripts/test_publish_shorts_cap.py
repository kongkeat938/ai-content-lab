#!/usr/bin/env python3
"""Guard the Shorts rail against a flood.

Measured 2026-11-05: a pool-grow commit triggered publish-shorts on push with no
per-run cap, so it uploaded 89 Shorts in one day. That day's median views fell to
1, against 206-1007 on drip days -- the Shorts feed throttles a channel that
floods. Two things allowed it, and this guard locks both:

  1. `--per-run` defaulted to 0 ("all due"). A missing cap must not mean "all".
  2. publish-shorts listed its own manifests under `push.paths`, so each publish
     re-triggered itself and a pool grow cascaded.

    python3 scripts/test_publish_shorts_cap.py    # exit 0 = safe
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "publish_shorts.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "publish-shorts.yml")
MAX_DEFAULT = 5  # a drip; anything larger is a flood in waiting


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    src = open(SCRIPT, encoding="utf-8").read()
    m = re.search(r'add_argument\("--per-run",\s*type=int,\s*default=(\d+)', src)
    if not m:
        fail("could not find the --per-run default in publish_shorts.py")
    default = int(m.group(1))
    if default == 0:
        fail("--per-run defaults to 0 = upload ALL due; a missing cap must not flood")
    if default > MAX_DEFAULT:
        fail(f"--per-run default {default} exceeds the safe drip ({MAX_DEFAULT})")

    m = re.search(r"MIN_GAP_HOURS\s*=\s*([\d.]+)", src)
    if not m:
        fail("publish_shorts.py has no MIN_GAP_HOURS; posts could go out back to back")
    gap = float(m.group(1))
    if gap < 1.0:
        fail(f"MIN_GAP_HOURS {gap} is too small to space posts apart")

    wf = open(WORKFLOW, encoding="utf-8").read()
    push = wf.split("push:", 1)[1].split("permissions:", 1)[0] if "push:" in wf else ""
    for line in push.splitlines():
        stripped = line.strip().lstrip("- ").strip().strip('"')
        if stripped.startswith("content/ch") and stripped.endswith("_shorts.json") \
                and "/shorts/" not in stripped:
            fail(f"push.paths lists the workflow's own output manifest: {stripped} "
                 "(each publish would re-trigger the next)")

    # K's rule (2026-11-09): one clip, wait, then read the result. The foreman must
    # never dispatch a run that posts more than one, or the "wait and check" step
    # has nothing to check -- the burst is what it exists to prevent.
    fm = open(os.path.join(HERE, "foreman.py"), encoding="utf-8").read()
    m = re.search(r'publish-shorts",\s*\{"per_run":\s*"(\d+)"', fm)
    if not m:
        fail("foreman.py does not dispatch publish-shorts with a per_run value")
    if int(m.group(1)) > 1:
        fail(f"foreman posts {m.group(1)} Shorts per dispatch; K's rule is one at a "
             "time (post, wait 2-3 h, read the result)")

    # The upload path labels every Short with hook_shape(), which lives in pace and
    # is imported inside a try (so the rail still runs when the gate cannot). That
    # made a NameError on the real upload path (measured 2026-11-10: genx Publish
    # step failed with "name 'hook_shape' is not defined"). publish_shorts must
    # define it at module scope, not rely on the guarded import.
    import ast
    tree = ast.parse(src)
    top = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if "hook_shape" not in top:
        fail("publish_shorts.py does not define hook_shape() at module scope; the "
             "upload path will NameError when pace is unavailable")
    if not re.search(r"hook_shape\(", src.split("def hook_shape", 1)[1]):
        fail("hook_shape() is defined but never called")

    print(f"OK: per-run default {default}, min gap {gap}h, no self-triggering manifest, "
          f"foreman posts {m.group(1)}/dispatch, hook_shape defined locally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
