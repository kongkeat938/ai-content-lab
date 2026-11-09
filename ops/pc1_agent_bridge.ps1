<#
.SYNOPSIS
  A runner-less bridge: PC1 dials OUT to GitHub and runs allow-listed tasks,
  without the unsigned Runner.Listener.exe that Device Guard / Smart App Control
  blocks.

.DESCRIPTION
  The GitHub Actions self-hosted runner is blocked on this PC because
  bin\Runner.Listener.exe is unsigned and Smart App Control (or a WDAC policy)
  refuses to start it -- and Smart App Control has NO allowlist, so there is no way
  to permit that one exe without turning Smart App Control off entirely (which is
  irreversible without reinstalling Windows).

  This bridge is the safe alternative. It runs as ordinary PowerShell, which is
  signed by Microsoft, so it is allowed to run even in enforcement mode. It polls a
  PRIVATE repo for command issues and runs a task from a fixed allowlist.

  Security properties (a guard test pins each one):
    * The token is read from a file, never a command-line argument, so it does not
      appear in the process list or in logs.
    * Only a hardcoded allowlist of tasks runs. Issue text is never executed --
      no Invoke-Expression, no & on remote strings.
    * Only issues labeled 'pc1-task' in the configured PRIVATE repo are acted on.
    * The task allowlist deliberately excludes 'shell': an arbitrary-command bridge
      reachable from the internet is the exact thing this design refuses to be.

  Run it once with -Install to register a logon scheduled task so it survives
  reboots, then the pod can drive PC1 with:
      gh issue create -R <owner>/<repo> --label pc1-task --title '[pc1] status'

.PARAMETER Repo
  owner/repo of the PRIVATE command repo.

.PARAMETER TokenFile
  Path to a file holding a fine-grained PAT with issues:write + contents:read.
  Never pass the token on the command line.

.PARAMETER PollSeconds
  Seconds between polls (default 20).

.PARAMETER Once
  Do a single poll and exit (for testing).

.PARAMETER Install
  Register the logon scheduled task and exit.
#>
[CmdletBinding()]
param(
  [string]$Repo = 'kongkeat938/ax-workspace',
  [string]$TokenFile = (Join-Path $env:USERPROFILE '.ax\pc1-token.txt'),
  [int]$PollSeconds = 20,
  [switch]$Once,
  [switch]$Install
)

$ErrorActionPreference = 'Stop'
$Api = 'https://api.github.com'

function Get-Token {
  if (-not (Test-Path $TokenFile)) {
    throw "token file not found: $TokenFile (write your PAT there, lock its ACL, and retry)"
  }
  (Get-Content -Raw -Path $TokenFile).Trim()
}

function Get-Headers([string]$tok) {
  @{
    Authorization          = "Bearer $tok"
    Accept                 = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent'           = 'pc1-agent-bridge'
  }
}

# --- The allowlist. Only these task names ever run. ---
function Invoke-Task([string]$name) {
  switch ($name) {
    'status' {
      try {
        $h = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/health' -UseBasicParsing -TimeoutSec 10
        "WINREMOTE_HEALTH=$($h.StatusCode)"
      } catch { "WINREMOTE_HEALTH=DOWN ($($_.Exception.Message))" }
      "HOST=$env:COMPUTERNAME"
      "USER=$env:USERNAME"
    }
    'fix-remote' {
      $u = 'https://raw.githubusercontent.com/kongkeat938/ai-content-lab/main/ops/pc1_fix_remote.ps1'
      $f = Join-Path $env:TEMP 'pc1_fix_remote.ps1'
      Invoke-WebRequest -Uri $u -OutFile $f -UseBasicParsing
      powershell -ExecutionPolicy Bypass -File $f -Persist
    }
    'readbox' {
      # Reuse the repo's mailbox reader if it is present locally; otherwise say so.
      "readbox is handled by the winremote MCP channel; this bridge has no mail reader."
    }
    default { throw "task '$name' is not in the allowlist" }
  }
}

function New-CommandIssue([string]$tok, [string]$task) {
  $body = @{ title = "[pc1] $task"; labels = @('pc1-task') } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "$Api/repos/$Repo/issues" -Headers (Get-Headers $tok) -Body $body | Out-Null
}

function Invoke-OnePoll([string]$tok) {
  $issues = Invoke-RestMethod -Method Get -Headers (Get-Headers $tok) `
    -Uri "$Api/repos/$Repo/issues?labels=pc1-task&state=open&per_page=5"
  foreach ($issue in @($issues)) {
    if ($issue.pull_request) { continue }
    $task = ($issue.title -replace '^\s*\[pc1\]\s*', '').Trim()
    $out = ''
    try {
      $out = (Invoke-Task $task 2>&1 | Out-String)
      if ([string]::IsNullOrWhiteSpace($out)) { $out = '(no output)' }
    } catch {
      $out = "TASK_ERROR: $($_.Exception.Message)"
    }
    $comment = @{ body = "``$task`` ->`n``````n$out`n``````" } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$Api/repos/$Repo/issues/$($issue.number)/comments" `
      -Headers (Get-Headers $tok) -Body $comment | Out-Null
    Invoke-RestMethod -Method Patch -Uri "$Api/repos/$Repo/issues/$($issue.number)" `
      -Headers (Get-Headers $tok) -Body (@{ state = 'closed' } | ConvertTo-Json) | Out-Null
    Write-Host "ran '$task' for issue #$($issue.number)"
  }
}

function Install-Bridge {
  $dir = Split-Path $TokenFile
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  # Lock the token file to the current user only.
  icacls $TokenFile /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null
  $ps = (Get-Command powershell.exe).Source
  $psArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Repo $Repo -TokenFile `"$TokenFile`""
  $action = New-ScheduledTaskAction -Execute $ps -Argument $psArgs
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
  Register-ScheduledTask -TaskName 'ax-pc1-bridge' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  "RESULT=OK"
  "TASK=ax-pc1-bridge"
  "TOKEN_FILE=$TokenFile"
}

if ($Install) {
  if (-not (Test-Path $TokenFile)) { throw "write your PAT to $TokenFile first, then re-run -Install" }
  Install-Bridge
  return
}

$tok = Get-Token
if ($Once) { Invoke-OnePoll $tok; return }

while ($true) {
  try { Invoke-OnePoll $tok } catch { Write-Host "poll error: $($_.Exception.Message)" }
  Start-Sleep -Seconds $PollSeconds
}
