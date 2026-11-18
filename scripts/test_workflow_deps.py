#!/usr/bin/env python3
"""Fail if a workflow runs a script whose dependency it never installs.

Two failures of the same shape, measured:

  2026-11-15: `.github/workflows/restore-wrongly-hidden.yml` ran
  `pip install -q google-api-python-client google-auth` and then
  `scripts/restore_wrongly_hidden.py --apply`. That script calls
  `yt_auth.load_credentials()`, whose `_require_google()` imports
  `google_auth_oauthlib.flow` -- a package that was NOT installed. The rail exited 1
  with "Missing google_auth_oauthlib" on every run, so the 5 wrongly-hidden clips were
  never restored, and `continue-on-error: true` hid the failure.

  2026-11-18: `set-thumbnails.yml` ran `scripts/set_thumbnails.py` with no install
  step. Adding `import numpy` (to compare the served thumbnail with our file) killed
  the rail at IMPORT -- `ModuleNotFoundError: No module named 'numpy'` -- so no
  thumbnail was ever installed. A rail can die at import; install its deps.

The rule, swept from the source (never a hardcoded workflow list):

  For each workflow, find every `scripts/<name>.py` it invokes. Read that script's own
  top-level imports. For each import that maps to a distribution in requirements.txt,
  the workflow must install that distribution (directly, or via `-r requirements.txt`,
  which lists them all). And if the script calls `load_credentials(`/`_require_google(`,
  the workflow must install `google-auth-oauthlib`.

Only modules that appear in requirements.txt are checked, so a stdlib or unknown
import is never a false alarm (K's rule: a false alarm is worse than no guard). A
transitive helper import (e.g. `optimize_titles` importing `audit_channels`) is NOT
followed -- only the script the workflow names, the same narrow scope as before.

It can FAIL: remove the install step from set-thumbnails.yml and it exits 1.

    python3 scripts/test_workflow_deps.py     # exit 0 = every run script has its deps
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")

# The package that provides google_auth_oauthlib.
OAUTH_DIST = "google-auth-oauthlib"
CALL_RE = re.compile(r"\b(?:load_credentials|_require_google)\s*\(")
SCRIPT_RE = re.compile(r"\bpython[0-9.]*\s+scripts/([A-Za-z0-9_]+)\.py")
# top-level `import x` / `from x import` (column 0), the script's own direct deps.
IMPORT_RE = re.compile(r"^(?:import|from)\s+([A-Za-z0-9_]+)", re.M)

# import root -> the distribution that provides it (as named in requirements.txt).
MODULE_DIST = {
    "numpy": "numpy",
    "PIL": "Pillow",
    "edge_tts": "edge-tts",
    "mcp": "mcp",
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "websocket": "websocket-client",
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def req_distributions() -> dict[str, str]:
    """Distribution name (lowercased) -> its canonical spelling in requirements.txt."""
    dists: dict[str, str] = {}
    if not os.path.exists(REQUIREMENTS):
        return dists
    for ln in open(REQUIREMENTS, encoding="utf-8"):
        m = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(?:[<>=!~]|$)", ln)
        if m and not ln.lstrip().startswith("#"):
            dists[m.group(1).lower()] = m.group(1)
    return dists


def scripts_run(text: str) -> set[str]:
    """Scripts the workflow actually invokes, not ones merely named in a comment."""
    names = set()
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        names.update(SCRIPT_RE.findall(ln))
    return names


def script_imports(name: str) -> set[str]:
    """Top-level import roots of scripts/<name>.py (its own direct deps)."""
    path = os.path.join(SCRIPTS, f"{name}.py")
    if not os.path.exists(path):
        return set()
    return set(IMPORT_RE.findall(open(path, encoding="utf-8").read()))


def script_calls_oauth(name: str) -> bool:
    """True if scripts/<name>.py calls load_credentials()/_require_google() itself."""
    path = os.path.join(SCRIPTS, f"{name}.py")
    if not os.path.exists(path):
        return False
    text = open(path, encoding="utf-8").read()
    # Ignore the definitions in yt_auth.py itself; a call site is what needs the dep.
    calls = [m for m in CALL_RE.finditer(text)]
    for m in calls:
        line = text[:m.start()].rsplit("\n", 1)[-1]
        if re.search(r"\bdef\s+(load_credentials|_require_google)\b", line):
            continue
        return True
    return False


def workflow_installs(text: str, dist: str, req_dists: dict[str, str]) -> bool:
    """True if the workflow installs `dist` (by name, or via -r requirements.txt)."""
    install_lines = [ln for ln in text.splitlines() if "pip install" in ln]
    want = dist.lower()
    for ln in install_lines:
        low = ln.lower()
        if want in low:
            return True
        # `-r requirements.txt` pulls in every distribution it lists.
        if "-r requirements.txt" in ln and want in req_dists:
            return True
    return False


def main() -> int:
    workflows = sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml")))
    if not workflows:
        fail("no workflow files found -- guard cannot see the repo")
    req_dists = req_distributions()
    problems = []
    checked = 0
    for wf in workflows:
        text = open(wf, encoding="utf-8").read()
        names = scripts_run(text)
        if not names:
            continue
        checked += 1
        missing: set[str] = set()
        for n in sorted(names):
            for root in script_imports(n):
                dist = MODULE_DIST.get(root)
                if dist and dist.lower() in req_dists and not workflow_installs(text, dist, req_dists):
                    missing.add(f"{dist} (scripts/{n}.py imports {root})")
            if script_calls_oauth(n) and not workflow_installs(text, OAUTH_DIST, req_dists):
                missing.add(f"{OAUTH_DIST} (scripts/{n}.py calls load_credentials/_require_google)")
        for m in sorted(missing):
            problems.append(f"{os.path.basename(wf)} runs a script but never installs {m}")
    if problems:
        fail("a workflow is missing a dependency its script needs:\n  "
             + "\n  ".join(problems))
    print(f"OK: every workflow's run-scripts have their installed deps "
          f"({checked} workflow(s) checked, {len(workflows)} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
