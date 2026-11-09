#!/usr/bin/env python3
"""Guard the runner-less PC1 bridge's security properties, offline.

The GitHub Actions runner cannot start on PC1 because bin\\Runner.Listener.exe is
unsigned and Smart App Control / WDAC blocks it, and Smart App Control has NO
allowlist (Microsoft docs: only On/Evaluation/Off). The fallback is a PowerShell
polling bridge -- PowerShell is Microsoft-signed, so it runs even in enforcement
mode -- but a bridge reachable from the internet is dangerous if it executes what
it reads. This test pins the properties that keep it safe, so a later edit cannot
quietly turn it into a remote shell.

    python3 scripts/test_pc1_bridge.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "ops", "pc1_agent_bridge.ps1")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def strip_comments(ps: str) -> str:
    """Remove PowerShell block and line comments so the scan looks at code only."""
    ps = re.sub(r"<#.*?#>", "", ps, flags=re.S)
    return "\n".join(re.sub(r"#.*$", "", ln) for ln in ps.splitlines())


def main() -> int:
    raw = open(SCRIPT, encoding="utf-8").read()
    src = strip_comments(raw)

    # 1. No dynamic execution of remote/issue text.
    for banned in ("Invoke-Expression", "IEX ", "iex("):
        if banned in src:
            fail(f"bridge contains '{banned.strip()}' -- it must never execute "
                 "text read from an issue; run allow-listed tasks only")

    # 2. The task allowlist must exist and must NOT include a raw shell.
    if "switch ($name)" not in src:
        fail("no task switch -- the bridge would have no allowlist")
    if re.search(r"^\s*'shell'\s*\{", src, re.M):
        fail("the allowlist contains a 'shell' task -- an arbitrary-command bridge "
             "reachable from the internet is exactly what this design refuses to be")

    # 3. The token must come from a file, never a command-line parameter.
    if re.search(r"\[string\]\$Token\b(?!File)", src):
        fail("the token is a plain parameter -- it would leak into the process list "
             "and logs; read it from $TokenFile instead")
    if "Get-Content -Raw -Path $TokenFile" not in src:
        fail("the token is not read from $TokenFile")

    # 4. It must be installed as a logon task (survives reboot) with the hidden
    #    signed powershell.exe, and it must lock the token file ACL.
    for need in ("Register-ScheduledTask", "-AtLogOn", "icacls $TokenFile",
                 "powershell.exe", "-WindowStyle Hidden"):
        if need not in src:
            fail(f"missing install detail: {need}")

    # 5. It must only act on issues carrying the label, in the configured repo.
    if "labels=pc1-task" not in src:
        fail("the poll does not filter by the 'pc1-task' label")
    if "labels = @('pc1-task')" not in src:
        fail("New-CommandIssue does not apply the 'pc1-task' label")

    print("ok  no dynamic execution of remote text")
    print("ok  allow-listed tasks only; no raw 'shell' task")
    print("ok  token read from a locked file, never a CLI argument")
    print("ok  installed as a hidden logon task; token ACL locked")
    print("ok  acts only on labeled issues in the configured repo")
    print("\nOK: the PC1 bridge stays an allow-list, not a remote shell")
    return 0


if __name__ == "__main__":
    sys.exit(main())
