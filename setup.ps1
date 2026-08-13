#Requires -Version 7.0
<#
.SYNOPSIS
    Windows dotfiles setup. Idempotent, resilient, runs unelevated.
.DESCRIPTION
    Every stage is safe to re-run. Failures are collected and reported at the
    end rather than aborting the run.

    Stages marked PENDING are placeholders until the tool list is agreed.
.PARAMETER SkipPreflight
    Skip the bootstrap.ps1 precondition check.
.PARAMETER SkipTerminal
    Skip Windows Terminal settings patching.
.EXAMPLE
    .\setup.ps1
    .\setup.ps1 -SkipPreflight
#>
[CmdletBinding()]
param(
    [switch]$SkipPreflight,
    [switch]$SkipTerminal
)

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'
$RepoRoot = $PSScriptRoot
$script:Errors = @()

function Write-Stage { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [OK] $m"   -ForegroundColor Green }
function Write-Skip  { param($m) Write-Host "  [SKIP] $m" -ForegroundColor DarkGray }
function Write-Warn2 { param($m) Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Write-Fail  { param($m) $script:Errors += $m; Write-Host "  [FAIL] $m" -ForegroundColor Red }

Write-Host ""
Write-Host "Windows dotfiles setup" -ForegroundColor Magenta
Write-Host "  repo: $RepoRoot" -ForegroundColor DarkGray

# ---------------------------------------------------------------- preflight
if (-not $SkipPreflight) {
    Write-Stage "Preflight"
    $bootstrap = Join-Path $RepoRoot 'bootstrap.ps1'
    if (Test-Path $bootstrap) {
        & $bootstrap
        if ($LASTEXITCODE -ne 0) {
            Write-Host "`nAborted. Fix the preconditions above and re-run." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Warn2 "bootstrap.ps1 missing, skipping preflight"
    }
}

# ---------------------------------------------------------------- scoop buckets
Write-Stage "Scoop buckets"
if (Get-Command scoop -ErrorAction SilentlyContinue) {
    $have = (scoop bucket list | Select-Object -ExpandProperty Name)
    foreach ($b in @('extras','nerd-fonts','versions')) {
        if ($have -contains $b) { Write-Skip "$b already added"; continue }
        scoop bucket add $b *> $null
        if ($LASTEXITCODE -eq 0) { Write-Ok "bucket $b" } else { Write-Fail "bucket $b" }
    }
} else {
    Write-Fail "scoop not found"
}

# ---------------------------------------------------------------- packages
Write-Stage "Packages"
Write-Skip "PENDING: winget and scoop manifests not defined yet"

# ---------------------------------------------------------------- config links
Write-Stage "Config links"
. (Join-Path $RepoRoot 'lib\link.ps1')
Write-Skip "PENDING: no config files to link yet"

# ---------------------------------------------------------------- terminal
if (-not $SkipTerminal) {
    Write-Stage "Windows Terminal"
    $patch = Join-Path $RepoRoot 'terminal\patch-settings.ps1'
    if (Test-Path $patch) { & $patch } else { Write-Warn2 "terminal\patch-settings.ps1 missing" }
}

# ---------------------------------------------------------------- summary
Write-Host ""
if ($script:Errors.Count -gt 0) {
    Write-Host "Completed with $($script:Errors.Count) issue(s):" -ForegroundColor Yellow
    $script:Errors | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
} else {
    Write-Host "Setup complete, no issues." -ForegroundColor Green
}

Write-Host "`nEnvironment:" -ForegroundColor Cyan
[ordered]@{
    'PowerShell' = $PSVersionTable.PSVersion.ToString()
    'winget'     = (winget --version 2>$null)
    'scoop'      = (if (Get-Command scoop -ErrorAction SilentlyContinue) { (scoop --version 2>$null | Select-Object -First 2 | Select-Object -Last 1) } else { $null })
    'git'        = (git --version 2>$null)
}.GetEnumerator() | ForEach-Object {
    $v = if ($_.Value) { $_.Value } else { 'not found' }
    Write-Host ("  {0,-12} {1}" -f $_.Key, $v)
}
Write-Host ""
