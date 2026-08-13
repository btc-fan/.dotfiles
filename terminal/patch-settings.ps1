<#
.SYNOPSIS
    Patches Windows Terminal settings.json in place.
.DESCRIPTION
    settings.json is NOT symlinked: Terminal rewrites the file whenever anything
    changes in the GUI, which would clobber a link. Instead we patch only the
    keys we care about and leave the rest of the user's settings alone.

    Idempotent. Backs up the file before the first modification.
#>
[CmdletBinding()]
param([switch]$WhatIfOnly)

$candidates = @(
    "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json",
    "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json",
    "$env:LOCALAPPDATA\Microsoft\Windows Terminal\settings.json"
)

$settingsPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $settingsPath) {
    Write-Host "  [SKIP] Windows Terminal settings.json not found. Launch Terminal once, then re-run." -ForegroundColor Yellow
    return
}

Write-Host "  settings: $settingsPath" -ForegroundColor DarkGray

try {
    $json = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
} catch {
    Write-Host "  [FAIL] could not parse settings.json: $($_.Exception.Message)" -ForegroundColor Red
    return
}

$changes = @()

# 1. Default profile -> PowerShell 7
$pwshProfile = $json.profiles.list | Where-Object {
    $_.commandline -match "pwsh" -or $_.source -eq "Windows.Terminal.PowershellCore" -or $_.name -eq "PowerShell"
} | Select-Object -First 1

if ($pwshProfile -and $json.defaultProfile -ne $pwshProfile.guid) {
    $json.defaultProfile = $pwshProfile.guid
    $changes += "defaultProfile -> $($pwshProfile.name)"
}
elseif (-not $pwshProfile) {
    Write-Host "  [WARN] no PowerShell 7 profile found in Terminal" -ForegroundColor Yellow
}

# 2. Paste warnings off. They block pasting multi-line scripts.
foreach ($key in @("multiLinePasteWarning","largePasteWarning")) {
    if ($json.PSObject.Properties.Name -notcontains $key -or $json.$key -ne $false) {
        $json | Add-Member -NotePropertyName $key -NotePropertyValue $false -Force
        $changes += "$key -> false"
    }
}

if ($changes.Count -eq 0) {
    Write-Host "  [SKIP] Terminal settings already correct" -ForegroundColor DarkGray
    return
}

if ($WhatIfOnly) {
    $changes | ForEach-Object { Write-Host "  [DRY] $_" -ForegroundColor DarkGray }
    return
}

$backup = "$settingsPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $settingsPath -Destination $backup -Force

$json | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $settingsPath -Encoding utf8

$changes | ForEach-Object { Write-Host "  [OK] $_" -ForegroundColor Green }
Write-Host "  backup: $backup" -ForegroundColor DarkGray
Write-Host "  restart Windows Terminal to apply" -ForegroundColor DarkGray
