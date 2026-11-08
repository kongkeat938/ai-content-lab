# pc1_install_runner.ps1 — give PC1 a permanent job channel to GitHub.
#
# Why this exists
# ---------------
# PC1 is the only machine that can read K's mail (its Chrome is already signed into
# all four accounts) and the only machine that can restart the winremote MCP server.
# The pod cannot dial in to PC1: there is no inbound route, no SSH, no tailnet in the
# pod, and the funnel answers 502 because the backend is down. Every rendezvous URL
# from an earlier session is dead too, because the pod is recycled and its hostname
# changes.
#
# A GitHub Actions self-hosted runner removes the problem for good. PC1 dials out to
# github.com (always reachable), and the pod dispatches a workflow that lands here.
# No port forward, no tunnel, no inbound rule, and the channel survives the pod being
# recycled -- the runner reconnects on its own.
#
# The runner is registered to a PRIVATE repository on purpose: a self-hosted runner
# on a public repository can be made to run code from a fork pull request, which is
# not something to put on someone's own machine.
#
# Run once, as Administrator. Idempotent: run it again to repair or update.
#
#   powershell -ExecutionPolicy Bypass -File pc1_install_runner.ps1 `
#     -RepoUrl https://github.com/<owner>/<private-repo> -Token <REGISTRATION_TOKEN>
#
# The token is a *registration* token, minted from the repository settings; it is
# short-lived (about one hour) and only good for adding a runner. It is not stored by
# this script -- after registration the runner authenticates with its own key, which
# never leaves the machine.

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$RepoUrl,
  [Parameter(Mandatory = $true)][string]$Token,
  [string]$Name = 'PC1',
  [string]$Labels = 'pc1',
  [string]$RunnerDir = 'C:\actions-runner',
  [string]$Version = '2.338.2',
  [string]$TaskName = 'ax-github-runner'
)

$ErrorActionPreference = 'Stop'

function Say([string]$m) { Write-Host "  $m" }
function Step([string]$m) { Write-Host ''; Write-Host "STEP=$m" }

# --- 0. Must be elevated: the download, the service and the scheduled task all need it.
$admin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'NOT_ADMIN: open PowerShell as Administrator and run again' }

Step 'paths'
New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
Say "runner dir = $RunnerDir"

# --- 1. Download the runner, only if it is not already unpacked.
$runCmd = Join-Path $RunnerDir 'run.cmd'
if (-not (Test-Path $runCmd)) {
  $zip = Join-Path $env:TEMP "actions-runner-win-x64-$Version.zip"
  $url = "https://github.com/actions/runner/releases/download/v$Version/actions-runner-win-x64-$Version.zip"
  Step 'download'
  Say "url = $url"
  if (-not (Test-Path $zip)) {
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  }
  Say "zip = $zip ($((Get-Item $zip).Length) bytes)"
  Step 'extract'
  Expand-Archive -Path $zip -DestinationPath $RunnerDir -Force
  Say 'extracted'
} else {
  Step 'download'
  Say "already present, skipping ($runCmd)"
}

# --- 2. Register. --replace takes over an existing registration with the same name,
#        which is what makes a re-run a repair rather than an error.
Step 'register'
Push-Location $RunnerDir
try {
  & .\config.cmd --url $RepoUrl --token $Token --name $Name --labels $Labels `
      --unattended --replace
  if ($LASTEXITCODE -ne 0) { throw "CONFIG_FAILED: exit $LASTEXITCODE" }
  Say 'registered'
} finally { Pop-Location }

# --- 3. Run at logon, as the signed-in user.
#        A Windows service would run as a service account, which cannot see the
#        user's Chrome profile or drive the desktop -- exactly what this channel is
#        for. A logon task runs in the user's own session.
Step 'scheduled task'
$action  = New-ScheduledTaskAction -Execute $runCmd -WorkingDirectory $RunnerDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Principal $principal -Settings $settings -Force | Out-Null
Say "task $TaskName registered"

# --- 4. Start it now, so the channel opens without a logoff.
Step 'start'
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 8
$state = (Get-ScheduledTask -TaskName $TaskName).State
Say "task state = $state"

# --- 5. Evidence. .runner holds the registration; its presence is the proof that
#        this machine is now a runner for the repository.
Step 'result'
$marker = Join-Path $RunnerDir '.runner'
if (Test-Path $marker) {
  $j = Get-Content $marker -Raw | ConvertFrom-Json
  Write-Host "RUNNER_NAME=$($j.agentName)"
  Write-Host "RUNNER_REPO=$($j.gitHubUrl)"
  Write-Host "RUNNER_TASK=$TaskName"
  Write-Host 'RESULT=OK'
} else {
  Write-Host 'RESULT=FAILED (no .runner marker; registration did not complete)'
  exit 1
}
Write-Host ''
Write-Host 'PC1 now has a permanent job channel. The pod can dispatch a workflow'
Write-Host 'labelled "pc1" and it will run here, with no inbound route needed.'
