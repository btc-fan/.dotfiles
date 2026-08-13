<#
.SYNOPSIS
    Fetches and launches Win11Debloat (Raphire) for interactive app removal.
.DESCRIPTION
    Win11Debloat is not on winget or Scoop. It is distributed from GitHub, so
    this wrapper clones it to a known location and launches it, rather than
    piping a remote script straight into the shell.

    The GUI is intentional: you choose what to remove. Blanket automated
    removal is how people lose the Microsoft Store and then cannot get it back.

    Repo: https://github.com/Raphire/Win11Debloat

    Every change Win11Debloat makes is reversible. Registry entries roll back
    and almost all removed apps can be reinstalled from the Store. The two
    exceptions are Microsoft Store itself and Xbox Speech-to-Text Overlay.

    IMPORTANT: Windows feature updates undo this work. Apps come back,
    telemetry re-enables, interface preferences reset. Re-run after every
    major update.
.PARAMETER Update
    Pull the latest version before launching.
.PARAMETER CLI
    Launch the text menu instead of the GUI.
.PARAMETER NoRestorePoint
    Skip creating a system restore point. Not recommended.
.EXAMPLE
    .\windows\debloat.ps1
.EXAMPLE
    .\windows\debloat.ps1 -Update
#>
[CmdletBinding()]
param(
    [switch]$Update,
    [switch]$CLI,
    [switch]$NoRestorePoint
)

$ErrorActionPreference = "Stop"

$repoUrl  = "https://github.com/Raphire/Win11Debloat.git"
$toolsDir = Join-Path $env:LOCALAPPDATA "dotfiles-tools"
$clonePath = Join-Path $toolsDir "Win11Debloat"

function Test-Elev {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Elev)) {
    Write-Host "`nWin11Debloat needs elevation to remove provisioned apps and" -ForegroundColor Red
    Write-Host "write policy keys. Run: Start-Process pwsh -Verb RunAs`n" -ForegroundColor Red
    exit 1
}

# ---------- restore point ----------
if (-not $NoRestorePoint) {
    Write-Host "`nCreating a system restore point..." -ForegroundColor Cyan
    try {
        Enable-ComputerRestore -Drive "C:\" -ErrorAction SilentlyContinue
        Checkpoint-Computer -Description "Pre-debloat $(Get-Date -Format 'yyyy-MM-dd HH:mm')" `
            -RestorePointType "MODIFY_SETTINGS" -ErrorAction Stop
        Write-Host "  [OK] restore point created" -ForegroundColor Green
    } catch {
        Write-Host "  [WARN] could not create a restore point: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  Windows rate-limits these to one per 24h. Continue only if you accept the risk." -ForegroundColor Yellow
        $ans = Read-Host "  Continue? (y/N)"
        if ($ans -ne "y") { exit 1 }
    }
}

# ---------- fetch ----------
New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null

if (Test-Path (Join-Path $clonePath ".git")) {
    if ($Update) {
        Write-Host "`nUpdating Win11Debloat..." -ForegroundColor Cyan
        Push-Location $clonePath
        git pull --ff-only 2>&1 | Out-Null
        Pop-Location
        Write-Host "  [OK] updated" -ForegroundColor Green
    } else {
        Write-Host "`nUsing existing clone. Pass -Update to refresh." -ForegroundColor DarkGray
    }
} else {
    Write-Host "`nCloning Win11Debloat to $clonePath ..." -ForegroundColor Cyan
    git clone --depth 1 $repoUrl $clonePath 2>&1 | Out-Null
    if (-not (Test-Path $clonePath)) {
        Write-Host "  [FAIL] clone failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] cloned" -ForegroundColor Green
}

Push-Location $clonePath
$commit = (git rev-parse --short HEAD 2>$null)
Pop-Location
Write-Host "  version: $commit" -ForegroundColor DarkGray

# ---------- reminders ----------
Write-Host "`nDO NOT REMOVE" -ForegroundColor Yellow
Write-Host "  Microsoft Store       winget msstore source needs it, unrecoverable" -ForegroundColor Gray
Write-Host "  App Installer         that IS winget" -ForegroundColor Gray
Write-Host "  WebView2 Runtime      Teams, Postman, most Electron apps break" -ForegroundColor Gray
Write-Host "  Microsoft Edge        WebView2 dependency" -ForegroundColor Gray
Write-Host "  Windows Terminal      this whole setup targets it" -ForegroundColor Gray
Write-Host "  .NET runtimes         obvious" -ForegroundColor Gray

Write-Host "`nSAFE TO REMOVE" -ForegroundColor Green
Write-Host "  Copilot, Recall, Click to Do, Widgets, Cortana" -ForegroundColor Gray
Write-Host "  Xbox apps, Solitaire, Clipchamp, 3D Viewer, Mixed Reality" -ForegroundColor Gray
Write-Host "  Weather, News, Bing Search, Teams Personal, OneDrive consumer" -ForegroundColor Gray
Write-Host "  Get Help, Tips, Feedback Hub, Maps, People" -ForegroundColor Gray

Write-Host "`nNote: Windows 11 Pro cannot fully disable telemetry. AllowTelemetry=0" -ForegroundColor DarkGray
Write-Host "is treated as 1 on Home and Pro; only Enterprise, Education, and" -ForegroundColor DarkGray
Write-Host "Server honour a true off. Required diagnostic data stays on." -ForegroundColor DarkGray

Write-Host "`nLaunching..." -ForegroundColor Cyan

$script = Join-Path $clonePath "Win11Debloat.ps1"
if (-not (Test-Path $script)) {
    Write-Host "  [FAIL] Win11Debloat.ps1 not found in the clone" -ForegroundColor Red
    exit 1
}

if ($CLI) { & $script -CLI } else { & $script }
