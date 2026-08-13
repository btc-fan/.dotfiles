<#
.SYNOPSIS
    Accurate MDM and Entra join state detection.
.DESCRIPTION
    Windows ships built-in enrollment scaffolding under
    HKLM\SOFTWARE\Microsoft\Enrollments that has EnrollmentState=1 on every
    machine. Naively counting those reports a clean device as enrolled.

    A genuine MDM enrollment is a GUID-named subkey carrying a real provider
    (typically "MS DM Server" for Intune), a UPN, and a discovery URL.
#>

$script:BuiltInProviders = @(
    "Local Authority"
    "Cloud Authority"
    "Deploy Authority"
    "WMI_Bridge_SCCM_Server"
)

function Get-MdmEnrollment {
    $root = "HKLM:\SOFTWARE\Microsoft\Enrollments"
    if (-not (Test-Path $root)) { return @() }

    Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
        # Real enrollments live under a GUID-named key
        if ($_.PSChildName -notmatch "^\{?[0-9A-Fa-f]{8}-([0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}\}?$") { return }

        $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
        if (-not $p) { return }
        if ($p.EnrollmentState -ne 1) { return }
        if (-not $p.ProviderID) { return }
        if ($script:BuiltInProviders -contains $p.ProviderID) { return }
        if (-not ($p.UPN -or $p.DiscoveryServiceFullURL)) { return }

        [pscustomobject]@{
            EnrollmentId = $_.PSChildName
            Provider     = $p.ProviderID
            UPN          = $p.UPN
            Discovery    = $p.DiscoveryServiceFullURL
            Type         = $p.EnrollmentType
        }
    }
}

function Get-JoinState {
    $raw = (dsregcmd /status 2>$null | Out-String)

    [pscustomobject]@{
        AzureAdJoined    = $raw -match "AzureAdJoined\s*:\s*YES"
        EnterpriseJoined = $raw -match "EnterpriseJoined\s*:\s*YES"
        DomainJoined     = $raw -match "DomainJoined\s*:\s*YES"
        WorkplaceJoined  = $raw -match "WorkplaceJoined\s*:\s*YES"
        MdmUrl           = $raw -match "MdmUrl\s*:\s*http"
        Raw              = $raw
    }
}

function Test-CorporateDevice {
    $j = Get-JoinState
    return ($j.AzureAdJoined -or $j.DomainJoined -or $j.EnterpriseJoined)
}

function Get-WorkplaceJoinBlockState {
    $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WorkplaceJoin"
    $val  = (Get-ItemProperty -Path $path -Name BlockAADWorkplaceJoin -ErrorAction SilentlyContinue).BlockAADWorkplaceJoin

    $task = $null
    try { $task = Get-ScheduledTask -TaskPath "\Microsoft\Windows\Workplace Join\" -TaskName "Automatic-Device-Join" -ErrorAction Stop } catch { }

    $triggersDisabled = $false
    if ($task) {
        $triggersDisabled = -not ($task.Triggers | Where-Object { $_.Enabled })
    }

    [pscustomobject]@{
        RegistryBlocked  = ($val -eq 1)
        TaskPresent      = ($null -ne $task)
        TriggersDisabled = $triggersDisabled
    }
}
