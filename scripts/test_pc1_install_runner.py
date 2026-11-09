#!/usr/bin/env python3
"""Guard the PC1 runner installer against the two bugs that broke the real install.

Bug 1 (2026-11-09): -Clean printed "removing C:\\actions-runner" and then
"already present and complete, skipping", because the completeness test ran on the
folder *before* the delete. The download was skipped, the folder was empty, and
register died with "config.cmd is not recognized". The delete must happen before
the test.

Bug 2: completeness was judged by run.cmd alone. config.cmd is only a wrapper for
bin\\Runner.Listener.exe; a truncated extract leaves run.cmd behind without bin\\,
so the download was skipped and config.cmd died with "The system cannot find the
file specified". Completeness must require the listener exe.

Both are checked against the shipped script text, offline.

    python3 scripts/test_pc1_install_runner.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "ops", "pc1_install_runner.ps1")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    src = open(SCRIPT, encoding="utf-8").read()

    # --- Bug 1: the -Clean delete must come before the completeness test. ---
    clean_i = src.find("if ($Clean) {")
    complete_i = src.find("$complete = (Test-Path $runCmd)")
    if clean_i == -1:
        fail("no 'if ($Clean) {' block -- -Clean would not delete anything")
    if complete_i == -1:
        fail("no '$complete = (Test-Path $runCmd)' line")
    if not clean_i < complete_i:
        fail("the -Clean delete is evaluated AFTER $complete -- this is exactly bug 1: "
             "the folder is wiped, the stale 'complete' verdict skips the download, "
             "and register fails with 'config.cmd is not recognized'")

    # The delete must not be guarded by a pre-delete completeness verdict.
    clean_block = src[clean_i:complete_i]
    if "Test-Path $listener" not in clean_block:
        fail("the -Clean block does not re-verify the delete -- a locked runner dir "
             "would be silently left in place and register would fail")

    # --- Bug 2: completeness must require the listener exe, not just run.cmd. ---
    if "$listener = Join-Path $RunnerDir 'bin\\Runner.Listener.exe'" not in src:
        fail("completeness does not name bin\\Runner.Listener.exe")
    if "$complete = (Test-Path $runCmd) -and (Test-Path $configCmd) -and (Test-Path $listener)" not in src:
        fail("$complete does not require the listener exe -- a partial extract would "
             "again be called complete and config.cmd would die with 'cannot find the file'")

    # --- Guard rails that make a future failure self-explaining. ---
    if "DOWNLOAD_INCOMPLETE" not in src:
        fail("no size gate on the downloaded zip -- a truncated zip looks fine by name")
    if "Get-Process Runner.Listener" not in src:
        fail("no hint for the locked-directory case")
    if src.count("$configCmd") < 2:
        fail("config.cmd is not invoked by full path")

    print("OK: -Clean deletes before the completeness test, completeness requires "
          "bin\\Runner.Listener.exe, and a bad download or locked dir names itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
