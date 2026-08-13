#Requires -Version 7.0
<#
.SYNOPSIS
    Updates everything to latest stable. No version pins anywhere.
.DESCRIPTION
    Safe to run any time. Updates winget packages, Scoop apps, Python and Node
    toolchains, uv tools, Azure CLI extensions, and PowerShell modules.
.EXAMPLE
    .\update.ps1
#>
[CmdletBinding()]
param([switch]$SkipRuntimes)

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"
$RepoRoot = $PSScriptRoot

. (Join-Path $RepoRoot "lib\common.ps1")

$started = Get-Date
Write-Host "`nUpdating everything to latest stable" -ForegroundColor Magenta

Write-Stage "winget"
winget source update 2>&1 | Out-Null
winget upgrade --all --include-unknown --silent `
    --accept-package-agreements --accept-source-agreements `
    --disable-interactivity 2>&1 | Out-Null
Write-Ok "winget upgrade --all"

Write-Stage "Scoop"
if (Test-Cmd scoop) {
    scoop update *>$null
    scoop update * *>$null
    scoop cleanup * *>$null
    Write-Ok "scoop apps updated and cleaned"
} else { Write-Fail "scoop not found" }

Update-SessionPath

if (-not $SkipRuntimes) {
    Write-Stage "Python"
    if (Test-Cmd pyenv) {
        pyenv update *>$null
        $latest = pyenv install -l 2>$null |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -match "^3\.\d+\.\d+$" } |
            Sort-Object { [version]$_ } | Select-Object -Last 1

        if ($latest) {
            $have = (pyenv versions 2>$null | Out-String)
            if ($have -notmatch [regex]::Escape($latest)) {
                pyenv install $latest *>$null
                Write-Ok "installed Python $latest"
            } else { Write-Skip "Python $latest present" }
            pyenv global $latest *>$null
            pyenv rehash *>$null
            Write-Ok "pyenv global -> $latest"
        } else { Write-Fail "could not determine latest Python" }
    }

    if (Test-Cmd uv) {
        uv self update 2>&1 | Out-Null
        uv python install 2>&1 | Out-Null
        uv tool upgrade --all 2>&1 | Out-Null
        Write-Ok "uv, managed Python, and uv tools"
    }

    Write-Stage "Node"
    if (Test-Cmd fnm) {
        fnm install --lts 2>&1 | Out-Null
        fnm default lts-latest 2>&1 | Out-Null
        Write-Ok "Node LTS refreshed"
    }

    Write-Stage "Azure CLI"
    if (Test-Cmd az) {
        az upgrade --yes --only-show-errors 2>&1 | Out-Null
        Write-Ok "az upgraded"
    }
}

Write-Stage "PowerShell modules"
foreach ($mod in @("PSReadLine","Terminal-Icons")) {
    if (Get-Module -ListAvailable -Name $mod) {
        try {
            Update-Module -Name $mod -Force -ErrorAction Stop
            Write-Ok $mod
        } catch { Write-Note "$mod : $($_.Exception.Message)" }
    }
}

$issues = Get-Issues
Write-Host ""
if ($issues.Count -gt 0) {
    Write-Host "$($issues.Count) issue(s):" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
} else {
    Write-Host ("Up to date. Took {0:mm}m {0:ss}s" -f ((Get-Date) - $started)) -ForegroundColor Green
}
Write-Host ""
