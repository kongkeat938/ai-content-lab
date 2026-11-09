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
  [string]$TaskName = 'ax-github-runner',
  [switch]$Clean
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

# config.cmd is only a wrapper for bin\Runner.Listener.exe. The unpack is complete
# only when that exe is present: a truncated extract leaves run.cmd/config.cmd
# behind without bin\, and then config.cmd dies with "The system cannot find the
# file specified" (exit 1) -- the failure seen on PC1.
$runCmd = Join-Path $RunnerDir 'run.cmd'
$configCmd = Join-Path $RunnerDir 'config.cmd'
$listener = Join-Path $RunnerDir 'bin\Runner.Listener.exe'
$zip = Join-Path $env:TEMP "actions-runner-win-x64-$Version.zip"
$url = "https://github.com/actions/runner/releases/download/v$Version/actions-runner-win-x64-$Version.zip"

# -Clean must wipe the folder BEFORE the completeness test. Computing $complete
# first and deleting second is what broke the PC1 run: it printed "removing
# C:\actions-runner" and then "already present and complete", because the test had
# read the folder that was about to be deleted, so the download was skipped and
# there was nothing left to register.
if ($Clean) {
  Step 'clean'
  Say "removing $RunnerDir (-Clean)"
  Remove-Item -Recurse -Force $RunnerDir -ErrorAction SilentlyContinue
  if (Test-Path $listener) {
    throw "CLEAN_FAILED: $listener survived the delete -- a runner process is locking it. Stop it (Stop-ScheduledTask $TaskName; Get-Process Runner.Listener -ErrorAction SilentlyContinue | Stop-Process -Force) and re-run."
  }
  New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
}

$complete = (Test-Path $runCmd) -and (Test-Path $configCmd) -and (Test-Path $listener)

# --- 1. Download and unpack unless the previous unpack is provably complete.
if (-not $complete) {
  Step 'download'
  Say "url = $url"
  # A truncated zip is indistinguishable from a good one by name, so fetch it
  # fresh whenever the unpack is incomplete, and refuse a zip that is too small.
  if (Test-Path $zip) { Remove-Item -Force $zip -ErrorAction SilentlyContinue }
  Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  $sizeMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
  Say "zip = $zip ($sizeMB MB)"
  if ($sizeMB -lt 50) { throw "DOWNLOAD_INCOMPLETE: only $sizeMB MB, expected ~100 MB -- re-run" }
  Step 'extract'
  Expand-Archive -Path $zip -DestinationPath $RunnerDir -Force
} else {
  Step 'download'
  Say 'already present and complete, skipping'
}

# --- 1b. Evidence of what is actually on disk, so a register failure can be
#         diagnosed from the log alone instead of from a bare exit code.
Step 'unpacked'
foreach ($f in @($runCmd, $configCmd, $listener)) {
  $mark = if (Test-Path $f) { 'OK     ' } else { 'MISSING' }
  Say "$mark $f"
}
if (-not (Test-Path $listener)) {
  throw "EXTRACT_INCOMPLETE: $listener is still missing -- re-run with -Clean"
}

# --- 2. Register. --replace takes over an existing registration with the same name,
#        which is what makes a re-run a repair rather than an error. The full config
#        output is echoed on failure, so a failed registration names its own cause
#        instead of only "exit 1".
Step 'register'
Push-Location $RunnerDir
try {
  & $configCmd --url $RepoUrl --token $Token --name $Name --labels $Labels `
      --unattended --replace 2>&1 | ForEach-Object { Say $_ }
  if ($LASTEXITCODE -ne 0) {
    throw "CONFIG_FAILED: exit $LASTEXITCODE (see the config output above; if it is a token problem, mint a fresh registration token and re-run)"
  }
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
