<#
.SYNOPSIS
    Prevents silent Entra registration and MDM enrollment on a PERSONAL device.
.DESCRIPTION
    Signing into a Microsoft 365 app such as Teams or Outlook on Windows shows
    "Allow my organization to manage my device", pre-checked. Accepting it
    registers the device with Entra and, if the tenant has automatic enrollment
    on, enrolls it into MDM. One checkbox in a login flow hands an employer
    management rights over personally owned hardware.

    This script blocks that path. Signing into individual apps still works:
    you get "Sign in to this app only" instead of device-wide registration.

    NOT run by setup.ps1. Invoke it deliberately.

    Two layers are applied:
      1. HKLM policy BlockAADWorkplaceJoin = 1
      2. Disabling the triggers on the Automatic-Device-Join scheduled task,
         which is more reliable than disabling the task itself

    SAFETY GUARD: refuses to run on a device that is already Entra joined,
    domain joined, or enterprise joined, since that indicates corporate
    hardware. Override with -Force only if you are certain you own the device.

    TRADEOFF: if your employer uses Conditional Access requiring a compliant or
    registered device, work resources will stop working on this machine. That
    is the intended result. Work data belongs on the work machine.
.PARAMETER Status
    Report current state. Changes nothing. Needs no elevation.
.PARAMETER Block
    Apply the block. Requires elevation.
.PARAMETER Unblock
    Reverse the block. Requires elevation.
.PARAMETER Force
    Bypass the corporate-device guard.
.EXAMPLE
    .\windows\block-mdm.ps1 -Status
.EXAMPLE
    .\windows\block-mdm.ps1 -Block
#>
[CmdletBinding(DefaultParameterSetName = "Status")]
param(
    [Parameter(ParameterSetName = "Status")][switch]$Status,
    [Parameter(ParameterSetName = "Block")][switch]$Block,
    [Parameter(ParameterSetName = "Unblock")][switch]$Unblock,
    [switch]$Force
)

$here = Split-Path -Parent $PSScriptRoot
. (Join-Path $here "lib\mdm.ps1")

$regPath  = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WorkplaceJoin"
$taskPath = "\Microsoft\Windows\Workplace Join\"
$taskName = "Automatic-Device-Join"

function Test-Elev {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Status {
    $join   = Get-JoinState
    $enroll = @(Get-MdmEnrollment)
    $block  = Get-WorkplaceJoinBlockState

    Write-Host "`nDevice join state" -ForegroundColor Cyan
    foreach ($k in @("AzureAdJoined","EnterpriseJoined","DomainJoined","WorkplaceJoined","MdmUrl")) {
        $v = $join.$k
        $color = if ($v) { "Yellow" } else { "Green" }
        Write-Host ("  {0,-18} {1}" -f $k, $(if ($v) { "YES" } else { "no" })) -ForegroundColor $color
    }

    Write-Host "`nMDM enrollment" -ForegroundColor Cyan
    if ($enroll.Count -eq 0) {
        Write-Host "  none" -ForegroundColor Green
    } else {
        foreach ($e in $enroll) {
            Write-Host "  ENROLLED" -ForegroundColor Yellow
            Write-Host "    provider:  $($e.Provider)"
            Write-Host "    account:   $($e.UPN)"
            Write-Host "    discovery: $($e.Discovery)"
        }
    }

    Write-Host "`nProtection" -ForegroundColor Cyan
    Write-Host ("  {0,-22} {1}" -f "1 WorkplaceJoin block", $(if ($block.RegistryBlocked) { "ON" } else { "off" })) `
        -ForegroundColor $(if ($block.RegistryBlocked) { "Green" } else { "Yellow" })
    Write-Host ("  {0,-22} {1}" -f "3 MDM registration", $(if ($block.MdmRegistrationBlocked) { "ON" } else { "off" })) `
        -ForegroundColor $(if ($block.MdmRegistrationBlocked) { "Green" } else { "Yellow" })
    if ($block.TaskPresent) {
        Write-Host ("  {0,-22} {1}" -f "2 Device-join task", $(if ($block.TriggersDisabled) { "disabled" } else { "ENABLED" })) `
            -ForegroundColor $(if ($block.TriggersDisabled) { "Green" } else { "Yellow" })
    } else {
        Write-Host ("  {0,-22} {1}" -f "2 Device-join task", "not present") -ForegroundColor DarkGray
    }
    Write-Host ""
}

if ($PSCmdlet.ParameterSetName -eq "Status" -or (-not $Block -and -not $Unblock)) {
    Show-Status
    $st = Get-WorkplaceJoinBlockState
    if ($st.RegistryBlocked -and $st.TriggersDisabled -and $st.MdmRegistrationBlocked) {
        Write-Host "All three layers active. Nothing to do." -ForegroundColor Green
    } else {
        Write-Host "Apply with:  .\windows\block-mdm.ps1 -Block   (elevated)" -ForegroundColor DarkGray
    }
    Write-Host ""
    return
}

if (-not (Test-Elev)) {
    Write-Host "This needs elevation. Run: Start-Process pwsh -Verb RunAs" -ForegroundColor Red
    exit 1
}

if ($Block) {
    if ((Test-CorporateDevice) -and -not $Force) {
        Write-Host "`nREFUSING TO RUN." -ForegroundColor Red
        Write-Host "This device is Entra joined, domain joined, or enterprise joined," -ForegroundColor Red
        Write-Host "which indicates corporate hardware. Removing management from an" -ForegroundColor Red
        Write-Host "employer-owned machine is a policy violation." -ForegroundColor Red
        Write-Host "`nIf you are certain you own this device, re-run with -Force.`n" -ForegroundColor DarkGray
        exit 1
    }

    Write-Host "`nBlocking automatic Entra registration and MDM enrollment" -ForegroundColor Cyan

    try {
        if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }
        New-ItemProperty -Path $regPath -Name BlockAADWorkplaceJoin -PropertyType DWord -Value 1 -Force | Out-Null
        Write-Host "  [OK]   BlockAADWorkplaceJoin = 1" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] registry: $($_.Exception.Message)" -ForegroundColor Red
    }

    try {
        $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction Stop
        $triggers = $task.Triggers
        if ($triggers) {
            foreach ($t in $triggers) { $t.Enabled = $false }
            Set-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Trigger $triggers -ErrorAction Stop | Out-Null
            Write-Host "  [OK]   Automatic-Device-Join triggers disabled ($($triggers.Count))" -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] task has no triggers" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  [WARN] scheduled task: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    # Layer 3: official Disable MDM Enrollment policy.
    # Blocks the enrollment stage outright. Matters because a second work
    # account from a different tenant has been observed enrolling a device
    # silently, with no prompt at all, and gaining remote wipe capability.
    try {
        $mdmPolicy = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CurrentVersion\MDM"
        if (-not (Test-Path $mdmPolicy)) { New-Item -Path $mdmPolicy -Force | Out-Null }
        New-ItemProperty -Path $mdmPolicy -Name DisableRegistration -PropertyType DWord -Value 1 -Force | Out-Null
        Write-Host "  [OK]   MDM enrollment disabled by policy" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] MDM policy: $($_.Exception.Message)" -ForegroundColor Red
    }

    Write-Host "`nDone. Teams and Outlook still work: choose 'Sign in to this app only'." -ForegroundColor Green
    Write-Host "If your employer requires a registered device for Conditional Access," -ForegroundColor DarkGray
    Write-Host "work resources will be blocked on this machine. That is expected.`n" -ForegroundColor DarkGray

    Show-Status
}

if ($Unblock) {
    Write-Host "`nRemoving the block" -ForegroundColor Cyan

    try {
        if (Test-Path $regPath) {
            Remove-ItemProperty -Path $regPath -Name BlockAADWorkplaceJoin -Force -ErrorAction SilentlyContinue
            Write-Host "  [OK]   BlockAADWorkplaceJoin removed" -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] policy key not present" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  [FAIL] registry: $($_.Exception.Message)" -ForegroundColor Red
    }

    try {
        $mdmPolicy = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CurrentVersion\MDM"
        if (Test-Path $mdmPolicy) {
            Remove-ItemProperty -Path $mdmPolicy -Name DisableRegistration -Force -ErrorAction SilentlyContinue
            Write-Host "  [OK]   MDM enrollment policy removed" -ForegroundColor Green
        }
    } catch { }

    try {
        $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction Stop
        $triggers = $task.Triggers
        if ($triggers) {
            foreach ($t in $triggers) { $t.Enabled = $true }
            Set-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Trigger $triggers -ErrorAction Stop | Out-Null
            Write-Host "  [OK]   task triggers re-enabled" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [WARN] scheduled task: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    Show-Status
}
