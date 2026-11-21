# Find .mp4 files under D:\MV-mp4 on PC1 and write a listing.
#
# Why a script and not a chat message: PC1 is unreachable from the pod on every
# route (tailnet funnel NXDOMAIN, self-hosted runner total_count 0, no tailscale
# in the pod, vault holds no endpoint -- measured 2026-11-20), so the only way to
# read D: is a human at the machine. A tested one-liner is the whole deliverable.
#
#   powershell -ExecutionPolicy Bypass -File .\find_mv_mp4.ps1
#
# Read-only: it lists, never moves or deletes.
#
# Written for Windows PowerShell 5.1 (the version Windows ships) as well as 7+:
#   * the listing is written with an explicit -Encoding utf8, because 5.1 defaults
#     Out-File to the ANSI code page -- TIS-620 on a Thai machine -- which mangles
#     every Thai filename (Gemini review, 2026-11-20);
#   * paths go through \\?\ so a file deeper than MAX_PATH (260) is still listed
#     instead of being silently dropped;
#   * -Filter does the extension match at the provider level.

[CmdletBinding()]
param(
    [string]$Root = 'D:\MV-mp4',
    [string]$Out = "$env:USERPROFILE\Desktop\mv-mp4-list.txt",
    [string]$Probe = ''      # a directory to stand in for D:\MV-mp4 in a test run
)

$ErrorActionPreference = 'Stop'
$scan = if ($Probe) { $Probe } else { $Root }

# Long-path form. Only for a real drive path -- prefixing a UNC or relative path
# with \\?\ makes it invalid, so those keep their own shape.
function Get-LongPath([string]$p) {
    if ($p -match '^[A-Za-z]:\\' -and -not $p.StartsWith('\\?\')) { return "\\?\$p" }
    return $p
}

$scanLong = Get-LongPath $scan

if (-not (Test-Path -LiteralPath $scanLong)) {
    $msg = "MISSING: $scan does not exist"
    $msg | Out-File -FilePath $Out -Encoding utf8
    $msg
    exit 2
}

# -LiteralPath, not -Path: a folder name with [ ] would otherwise be read as a
# wildcard and silently match nothing (a false "no files"). Measured 2026-11-20.
$files = Get-ChildItem -LiteralPath $scanLong -Recurse -File -Filter *.mp4 -Force -ErrorAction SilentlyContinue

if (-not $files) {
    $msg = "EMPTY: no .mp4 under $scan"
    $msg | Out-File -FilePath $Out -Encoding utf8
    $msg
    exit 3
}

$total = ($files | Measure-Object -Property Length -Sum).Sum
$lines = @(
    "ROOT=$scan"
    "COUNT=$($files.Count)"
    "TOTAL_GB=$([math]::Round($total / 1GB, 2))"
    ''
    $files |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object {
            $when = $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
            $mb = '{0,10:N1} MB' -f ($_.Length / 1MB)
            # Strip the \\?\ prefix so the path can be pasted into Explorer.
            $shown = $_.FullName -replace '^\\\\\?\\', ''
            (@($when, $mb, $shown) -join "`t")
        }
)

# utf8 (with BOM in 5.1) is what Notepad and Excel open correctly on Thai Windows.
$lines | Out-File -FilePath $Out -Encoding utf8
$lines
"WROTE=$Out"
