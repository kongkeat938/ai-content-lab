#!/usr/bin/env python3
"""Fail if a workflow runs a script whose Google OAuth dependency it never installs.

Measured 2026-11-15: `.github/workflows/restore-wrongly-hidden.yml` ran
`pip install -q google-api-python-client google-auth` and then
`scripts/restore_wrongly_hidden.py --apply`. That script calls
`yt_auth.load_credentials()`, whose `_require_google()` imports
`google_auth_oauthlib.flow` -- a package that was NOT installed. The rail exited 1
with "Missing google_auth_oauthlib" on every run, so the 5 wrongly-hidden clips were
never restored, and `continue-on-error: true` hid the failure. Sibling workflows
(account-watch, rogue-guard, short-doors) installed it correctly; this one drifted.

The rule, swept from the source (never a hardcoded workflow list):

  For each workflow, find every `scripts/<name>.py` it invokes. If that script's own
  source calls `load_credentials(` or `_require_google(`, the workflow must install
  `google-auth-oauthlib` (directly, or via `-r requirements.txt`, which lists it).

This is deliberately narrow: it keys on a *direct* call in the script the workflow
runs, so a workflow that merely imports a helper (e.g. `optimize_titles` importing
`recorded_ids` from audit_channels) is not flagged -- that import does not touch
OAuth. A false alarm here would be worse than no guard (K's rule).

It can FAIL: remove `google-auth-oauthlib` from restore-wrongly-hidden.yml and it
exits 1.

    python3 scripts/test_workflow_deps.py     # exit 0 = every OAuth script has its dep
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

# The package that provides google_auth_oauthlib, and the requirements line that
# also satisfies it.
OAUTH_DIST = "google-auth-oauthlib"
OAUTH_IMPORT = "google_auth_oauthlib"
CALL_RE = re.compile(r"\b(?:load_credentials|_require_google)\s*\(")
SCRIPT_RE = re.compile(r"\bpython[0-9.]*\s+scripts/([A-Za-z0-9_]+)\.py")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def scripts_run(text: str) -> set[str]:
    """Scripts the workflow actually invokes, not ones merely named in a comment."""
    names = set()
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        names.update(SCRIPT_RE.findall(ln))
    return names


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


def workflow_installs_oauth(text: str) -> bool:
    # Only look at the pip install lines -- a comment that merely names the package
    # must not satisfy the guard.
    install_lines = [ln for ln in text.splitlines() if "pip install" in ln]
    for ln in install_lines:
        if OAUTH_DIST in ln or OAUTH_IMPORT in ln:
            return True
        # `-r requirements.txt` pulls it in, because requirements.txt lists it.
        if "-r requirements.txt" in ln:
            req = os.path.join(ROOT, "requirements.txt")
            if os.path.exists(req) and OAUTH_DIST in open(req, encoding="utf-8").read():
                return True
    return False


def main() -> int:
    workflows = sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml")))
    if not workflows:
        fail("no workflow files found -- guard cannot see the repo")
    problems = []
    checked = 0
    for wf in workflows:
        text = open(wf, encoding="utf-8").read()
        names = scripts_run(text)
        oauth_scripts = [n for n in sorted(names) if script_calls_oauth(n)]
        if not oauth_scripts:
            continue
        checked += 1
        if not workflow_installs_oauth(text):
            problems.append(
                f"{os.path.basename(wf)} runs {', '.join('scripts/' + n + '.py' for n in oauth_scripts)}"
                f" (calls load_credentials/_require_google) but never installs {OAUTH_DIST}")
    if problems:
        fail("a workflow is missing the Google OAuth dependency its script needs:\n  "
             + "\n  ".join(problems))
    print(f"OK: every workflow that runs an OAuth script installs {OAUTH_DIST} "
          f"({checked} workflow(s) checked, {len(workflows)} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
