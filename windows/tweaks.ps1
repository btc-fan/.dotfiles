<#
.SYNOPSIS
    Explorer and shell preferences. The macOS `defaults write` equivalent.
.DESCRIPTION
    All HKCU, so no elevation needed. Idempotent: only writes what differs, and
    only restarts Explorer if something actually changed.
.PARAMETER NoRestart
    Apply settings but do not restart Explorer. Changes appear after next logon.
#>
[CmdletBinding()]
param([switch]$NoRestart, [switch]$WhatIfOnly)

$changed = 0

function Set-Pref {
    param([string]$Path, [string]$Name, $Value, [string]$Type = "DWORD", [string]$Label)

    $current = (Get-ItemProperty -Path $Path -Name $Name -ErrorAction SilentlyContinue).$Name
    if ($null -ne $current -and $current -eq $Value) {
        Write-Host "  [SKIP] $Label" -ForegroundColor DarkGray
        return
    }
    if ($WhatIfOnly) {
        Write-Host "  [DRY]  $Label (is '$current', would be '$Value')" -ForegroundColor DarkGray
        return
    }
    try {
        if (-not (Test-Path $Path)) { New-Item -Path $Path -Force | Out-Null }
        New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null
        Write-Host "  [OK]   $Label" -ForegroundColor Green
        $script:changed++
    } catch {
        Write-Host "  [FAIL] $Label : $($_.Exception.Message)" -ForegroundColor Red
    }
}

$adv      = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
$cabinet  = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\CabinetState"
$personal = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"

# The two you asked for explicitly
Set-Pref -Path $adv -Name Hidden      -Value 1 -Label "Show hidden files and folders"
Set-Pref -Path $adv -Name HideFileExt -Value 0 -Label "Show file extensions for known types"

# Supporting Explorer behaviour
Set-Pref -Path $cabinet -Name FullPath -Value 1 -Label "Full path in the title bar"
Set-Pref -Path $adv -Name LaunchTo              -Value 1 -Label "Explorer opens to This PC"
Set-Pref -Path $adv -Name NavPaneShowAllFolders -Value 1 -Label "Show all folders in the nav pane"
Set-Pref -Path $adv -Name ShowTaskViewButton    -Value 0 -Label "Hide the Task View button"

# Appearance
Set-Pref -Path $personal -Name AppsUseLightTheme   -Value 0 -Label "Dark mode (apps)"
Set-Pref -Path $personal -Name SystemUsesLightTheme -Value 0 -Label "Dark mode (system)"

# Stop the Start menu searching the web
Set-Pref -Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer" `
    -Name DisableSearchBoxSuggestions -Value 1 -Label "Disable Start menu web search"

# NOT enabled by default: showing protected OS files clutters every folder with
# desktop.ini and pagefile.sys. Uncomment if you want it.
# Set-Pref -Path $adv -Name ShowSuperHidden -Value 1 -Label "Show protected OS files"

if ($WhatIfOnly) { return }

if ($changed -eq 0) {
    Write-Host "  nothing to change" -ForegroundColor DarkGray
    return
}

if ($NoRestart) {
    Write-Host "  $changed change(s). Restart Explorer or sign out to apply." -ForegroundColor Yellow
} else {
    Write-Host "  $changed change(s), restarting Explorer..." -ForegroundColor DarkGray
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
    if (-not (Get-Process -Name explorer -ErrorAction SilentlyContinue)) {
        Start-Process explorer
    }
    Write-Host "  [OK]   Explorer restarted" -ForegroundColor Green
}
