<#
.SYNOPSIS
    Privacy and telemetry controls. Complements Win11Debloat.
.DESCRIPTION
    Win11Debloat handles app removal and most of this. This script exists for
    the pieces that need to be enforced at policy level so they survive
    Windows updates, and so you have an auditable, reversible record of exactly
    what was changed on your machine.

    Every setting below is listed explicitly with its registry path. Nothing is
    hidden. Run -Status first to see current state before changing anything.

    HONEST LIMIT: on Windows 11 Home and Pro you cannot disable telemetry.
    Microsoft treats AllowTelemetry=0 as 1 on these editions, so Required
    diagnostic data (hardware config, crash reports, update info) keeps
    flowing. Only Enterprise, Education, and Server honour a true off. What
    this script does is cap collection at the lowest level your edition
    permits and stop the optional layers. That is a real reduction, not a
    complete shutdown, and anyone telling you otherwise is wrong.

    Windows Update, Defender, and security patching are unaffected. Telemetry
    level 0 has been a supported configuration since Windows 10 1607.

    Originals are captured to .privacy-original.json before any change, so
    -Revert restores what you actually had rather than a guessed default.
.PARAMETER Status
    Report current state. Read-only, no elevation needed.
.PARAMETER Apply
    Apply the settings. Requires elevation.
.PARAMETER Revert
    Restore captured originals. Requires elevation.
.PARAMETER Category
    Limit to one category: Telemetry, Advertising, Suggestions, AI, Location, Services
.EXAMPLE
    .\windows\privacy.ps1 -Status
.EXAMPLE
    .\windows\privacy.ps1 -Apply
.EXAMPLE
    .\windows\privacy.ps1 -Apply -Category AI
#>
[CmdletBinding(DefaultParameterSetName = "Status")]
param(
    [Parameter(ParameterSetName = "Status")][switch]$Status,
    [Parameter(ParameterSetName = "Apply")][switch]$Apply,
    [Parameter(ParameterSetName = "Revert")][switch]$Revert,
    [ValidateSet("Telemetry","Advertising","Suggestions","AI","Location","Services")]
    [string]$Category
)

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$backupFile = Join-Path $RepoRoot ".privacy-original.json"

# =====================================================================
# Registry settings. Each entry is explicit and auditable.
# Desired = what we set it to. Default = documented Windows default.
# =====================================================================
$tweaks = @(

    # ---------- Telemetry ----------
    @{ Category = "Telemetry"; Label = "Diagnostic data level (policy cap)"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
       Name = "AllowTelemetry"; Desired = 0; Default = $null
       Note = "Capped at Required on Pro. Greys out the Settings toggle." }

    @{ Category = "Telemetry"; Label = "Do not show feedback notifications"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
       Name = "DoNotShowFeedbackNotifications"; Desired = 1; Default = $null }

    @{ Category = "Telemetry"; Label = "Limit diagnostic log collection"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
       Name = "LimitDiagnosticLogCollection"; Desired = 1; Default = $null }

    @{ Category = "Telemetry"; Label = "Limit dump collection"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
       Name = "LimitDumpCollection"; Desired = 1; Default = $null }

    @{ Category = "Telemetry"; Label = "Disable tailored experiences"
       Path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"
       Name = "DisableTailoredExperiencesWithDiagnosticData"; Desired = 1; Default = $null }

    @{ Category = "Telemetry"; Label = "Activity history: do not upload"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System"
       Name = "UploadUserActivities"; Desired = 0; Default = $null }

    @{ Category = "Telemetry"; Label = "Activity history: do not publish"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System"
       Name = "PublishUserActivities"; Desired = 0; Default = $null }

    @{ Category = "Telemetry"; Label = "Inventory collector off"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppCompat"
       Name = "DisableInventory"; Desired = 1; Default = $null }

    # ---------- Advertising ----------
    @{ Category = "Advertising"; Label = "Advertising ID disabled"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo"
       Name = "DisabledByGroupPolicy"; Desired = 1; Default = $null }

    @{ Category = "Advertising"; Label = "Advertising ID (per user)"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo"
       Name = "Enabled"; Desired = 0; Default = 1 }

    @{ Category = "Advertising"; Label = "App launch tracking off"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
       Name = "Start_TrackProgs"; Desired = 0; Default = 1 }

    # ---------- Suggestions, tips, ads in the shell ----------
    @{ Category = "Suggestions"; Label = "Windows Spotlight features off"
       Path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"
       Name = "DisableWindowsSpotlightFeatures"; Desired = 1; Default = $null }

    @{ Category = "Suggestions"; Label = "Third-party suggestions off"
       Path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"
       Name = "DisableThirdPartySuggestions"; Desired = 1; Default = $null }

    @{ Category = "Suggestions"; Label = "Consumer features off (auto-installed apps)"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"
       Name = "DisableWindowsConsumerFeatures"; Desired = 1; Default = $null }

    @{ Category = "Suggestions"; Label = "Start menu suggestions"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
       Name = "SystemPaneSuggestionsEnabled"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Silent app install"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
       Name = "SilentInstalledAppsEnabled"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Pre-installed apps"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
       Name = "PreInstalledAppsEnabled"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Lock screen suggestions"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
       Name = "RotatingLockScreenOverlayEnabled"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Settings app suggestions"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
       Name = "SubscribedContent-338393Enabled"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Tips and tricks notifications"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
       Name = "SubscribedContent-338389Enabled"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Start menu account notifications"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
       Name = "Start_AccountNotifications"; Desired = 0; Default = 1 }

    @{ Category = "Suggestions"; Label = "Bing search in Start menu"
       Path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer"
       Name = "DisableSearchBoxSuggestions"; Desired = 1; Default = $null }

    # ---------- AI features ----------
    @{ Category = "AI"; Label = "Copilot disabled"
       Path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"
       Name = "TurnOffWindowsCopilot"; Desired = 1; Default = $null }

    @{ Category = "AI"; Label = "Recall: disable analysis"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
       Name = "DisableAIDataAnalysis"; Desired = 1; Default = $null }

    @{ Category = "AI"; Label = "Recall: disable saving snapshots"
       Path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
       Name = "DisableAIDataAnalysis"; Desired = 1; Default = $null }

    @{ Category = "AI"; Label = "Click to Do disabled"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
       Name = "DisableClickToDo"; Desired = 1; Default = $null }

    @{ Category = "AI"; Label = "Copilot button hidden from taskbar"
       Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
       Name = "ShowCopilotButton"; Desired = 0; Default = 1 }

    # ---------- Location ----------
    @{ Category = "Location"; Label = "Location services disabled"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors"
       Name = "DisableLocation"; Desired = 1; Default = $null }

    @{ Category = "Location"; Label = "Location scripting disabled"
       Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors"
       Name = "DisableLocationScripting"; Desired = 1; Default = $null }
)

# Services to disable. DiagTrack is the main telemetry conduit.
$services = @(
    @{ Category = "Services"; Name = "DiagTrack";         Label = "Connected User Experiences and Telemetry" }
    @{ Category = "Services"; Name = "dmwappushservice";  Label = "WAP Push Message Routing" }
)

# =====================================================================
function Test-Elev {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-Current {
    param($t)
    (Get-ItemProperty -Path $t.Path -Name $t.Name -ErrorAction SilentlyContinue).$($t.Name)
}

function Select-Tweaks {
    if ($Category) { $tweaks | Where-Object { $_.Category -eq $Category } } else { $tweaks }
}
function Select-Services {
    if ($Category -and $Category -ne "Services") { @() }
    else { $services }
}

function Show-Status {
    $lastCat = ""
    foreach ($t in (Select-Tweaks)) {
        if ($t.Category -ne $lastCat) {
            Write-Host "`n  $($t.Category)" -ForegroundColor Cyan
            $lastCat = $t.Category
        }
        $cur = Get-Current $t
        $set = ($null -ne $cur -and $cur -eq $t.Desired)
        $curText = if ($null -eq $cur) { "not set" } else { $cur }
        Write-Host ("    {0,-8} {1,-46} {2}" -f $(if ($set) { "[ON]" } else { "[off]" }), $t.Label, $curText) `
            -ForegroundColor $(if ($set) { "Green" } else { "DarkGray" })
    }

    $svc = Select-Services
    if ($svc.Count -gt 0) {
        Write-Host "`n  Services" -ForegroundColor Cyan
        foreach ($s in $svc) {
            $o = Get-Service -Name $s.Name -ErrorAction SilentlyContinue
            if (-not $o) {
                Write-Host ("    {0,-8} {1,-46} {2}" -f "[--]", $s.Label, "not present") -ForegroundColor DarkGray
                continue
            }
            $disabled = $o.StartType -eq "Disabled"
            Write-Host ("    {0,-8} {1,-46} {2} / {3}" -f $(if ($disabled) { "[ON]" } else { "[off]" }), $s.Label, $o.Status, $o.StartType) `
                -ForegroundColor $(if ($disabled) { "Green" } else { "DarkGray" })
        }
    }
    Write-Host ""
}

# ---------------------------------------------------------------- STATUS
if ($PSCmdlet.ParameterSetName -eq "Status" -or (-not $Apply -and -not $Revert)) {
    Write-Host "`nPrivacy settings status" -ForegroundColor Magenta
    Write-Host "  edition: $((Get-CimInstance Win32_OperatingSystem).Caption)" -ForegroundColor DarkGray
    Write-Host "  note:    Home and Pro cannot fully disable telemetry. Required data stays on." -ForegroundColor DarkGray
    Show-Status
    Write-Host "Apply with:  .\windows\privacy.ps1 -Apply   (elevated)`n" -ForegroundColor DarkGray
    return
}

if (-not (Test-Elev)) {
    Write-Host "`nNeeds elevation. Run: Start-Process pwsh -Verb RunAs`n" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- APPLY
if ($Apply) {
    Write-Host "`nApplying privacy settings" -ForegroundColor Magenta

    # Capture originals once, before anything changes.
    $original = @{}
    if (Test-Path $backupFile) {
        try {
            $raw = Get-Content $backupFile -Raw | ConvertFrom-Json
            foreach ($p in $raw.PSObject.Properties) { $original[$p.Name] = $p.Value }
            Write-Host "  using existing capture from $backupFile" -ForegroundColor DarkGray
        } catch { $original = @{} }
    }

    $applied = 0
    $lastCat = ""
    foreach ($t in (Select-Tweaks)) {
        if ($t.Category -ne $lastCat) { Write-Host "`n  $($t.Category)" -ForegroundColor Cyan; $lastCat = $t.Category }

        $key = "$($t.Path)|$($t.Name)"
        $cur = Get-Current $t

        if (-not $original.ContainsKey($key)) {
            $original[$key] = @{ value = $cur; existed = ($null -ne $cur) }
        }

        if ($null -ne $cur -and $cur -eq $t.Desired) {
            Write-Host "    [SKIP] $($t.Label)" -ForegroundColor DarkGray
            continue
        }

        try {
            if (-not (Test-Path $t.Path)) { New-Item -Path $t.Path -Force | Out-Null }
            New-ItemProperty -Path $t.Path -Name $t.Name -Value $t.Desired -PropertyType DWord -Force | Out-Null
            Write-Host "    [OK]   $($t.Label)" -ForegroundColor Green
            $applied++
        } catch {
            Write-Host "    [FAIL] $($t.Label): $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    $svc = Select-Services
    if ($svc.Count -gt 0) {
        Write-Host "`n  Services" -ForegroundColor Cyan
        foreach ($s in $svc) {
            $o = Get-Service -Name $s.Name -ErrorAction SilentlyContinue
            if (-not $o) { Write-Host "    [SKIP] $($s.Label) not present" -ForegroundColor DarkGray; continue }

            $key = "service|$($s.Name)"
            if (-not $original.ContainsKey($key)) {
                $original[$key] = @{ value = $o.StartType.ToString(); existed = $true }
            }

            if ($o.StartType -eq "Disabled") {
                Write-Host "    [SKIP] $($s.Label) already disabled" -ForegroundColor DarkGray
                continue
            }
            try {
                Stop-Service -Name $s.Name -Force -ErrorAction SilentlyContinue
                Set-Service -Name $s.Name -StartupType Disabled -ErrorAction Stop
                Write-Host "    [OK]   $($s.Label) stopped and disabled" -ForegroundColor Green
                $applied++
            } catch {
                Write-Host "    [FAIL] $($s.Label): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }

    $original | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $backupFile -Encoding utf8

    Write-Host "`n  $applied change(s). Originals captured to .privacy-original.json" -ForegroundColor Green
    Write-Host "  Sign out and back in, or reboot, for all of it to take effect." -ForegroundColor DarkGray
    Write-Host "  Re-run after every major Windows feature update: they reset this.`n" -ForegroundColor DarkGray
    return
}

# ---------------------------------------------------------------- REVERT
if ($Revert) {
    if (-not (Test-Path $backupFile)) {
        Write-Host "`nNo capture file found at $backupFile. Nothing to revert to.`n" -ForegroundColor Red
        exit 1
    }

    Write-Host "`nReverting to captured originals" -ForegroundColor Magenta
    $raw = Get-Content $backupFile -Raw | ConvertFrom-Json
    $reverted = 0

    foreach ($p in $raw.PSObject.Properties) {
        $key = $p.Name
        $rec = $p.Value

        if ($key -like "service|*") {
            $name = $key.Split("|")[1]
            try {
                Set-Service -Name $name -StartupType $rec.value -ErrorAction Stop
                Write-Host "  [OK]   service $name -> $($rec.value)" -ForegroundColor Green
                $reverted++
            } catch {
                Write-Host "  [FAIL] service $name : $($_.Exception.Message)" -ForegroundColor Red
            }
            continue
        }

        $parts = $key.Split("|")
        $path = $parts[0]; $valName = $parts[1]

        try {
            if ($rec.existed) {
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                New-ItemProperty -Path $path -Name $valName -Value $rec.value -PropertyType DWord -Force | Out-Null
                Write-Host "  [OK]   $valName -> $($rec.value)" -ForegroundColor Green
            } else {
                if (Test-Path $path) {
                    Remove-ItemProperty -Path $path -Name $valName -Force -ErrorAction SilentlyContinue
                }
                Write-Host "  [OK]   $valName removed (was not set)" -ForegroundColor Green
            }
            $reverted++
        } catch {
            Write-Host "  [FAIL] $valName : $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    Write-Host "`n  $reverted item(s) reverted. Reboot to apply.`n" -ForegroundColor Green
}
