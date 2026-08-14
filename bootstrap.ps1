<#
.SYNOPSIS
    Verifies every manual precondition. Read-only, changes nothing.
.DESCRIPTION
    Exits 0 when the machine is ready for setup.ps1, 1 otherwise.
    Deliberately has no #Requires so it can run under Windows PowerShell 5.1
    and tell you why that is a problem.
#>
[CmdletBinding()]
param([switch]$Quiet)

$ErrorActionPreference = 'Continue'
$script:Failures = @()
$script:Warnings = @()

function Test-Precondition {
    param(
        [string]$Name,
        [scriptblock]$Check,
        [string]$Fix,
        [switch]$AsWarning
    )
    $ok = $false
    try { $ok = [bool](& $Check) } catch { $ok = $false }

    if ($ok) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
    }
    elseif ($AsWarning) {
        Write-Host "  [WARN] $Name" -ForegroundColor Yellow
        $script:Warnings += @{ Name = $Name; Fix = $Fix }
    }
    else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        $script:Failures += @{ Name = $Name; Fix = $Fix }
    }
}

Write-Host ""
Write-Host "Windows dotfiles: precondition check" -ForegroundColor Cyan
Write-Host ""

Test-Precondition -Name "Windows 10 22H2 / Windows 11 or newer" `
    -Check { [System.Environment]::OSVersion.Version.Build -ge 19045 } `
    -Fix "Settings > Windows Update"

Test-Precondition -Name "PowerShell 7+ (running $($PSVersionTable.PSVersion))" `
    -Check { $PSVersionTable.PSVersion.Major -ge 7 } `
    -Fix "winget install --id Microsoft.PowerShell -e ; then open a PowerShell (black icon) tab"

Test-Precondition -Name "winget available" `
    -Check { $null -ne (Get-Command winget -ErrorAction SilentlyContinue) } `
    -Fix "Install App Installer from the Microsoft Store"

Test-Precondition -Name "Execution policy permits local scripts" `
    -Check { (Get-ExecutionPolicy -Scope CurrentUser) -in @("RemoteSigned","Unrestricted","Bypass") } `
    -Fix "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"

Test-Precondition -Name "Scoop available" `
    -Check { $null -ne (Get-Command scoop -ErrorAction SilentlyContinue) } `
    -Fix "irm get.scoop.sh | iex"

Test-Precondition -Name "Git available" `
    -Check { $null -ne (Get-Command git -ErrorAction SilentlyContinue) } `
    -Fix "winget install --id Git.Git -e"

Test-Precondition -Name "Git identity configured" `
    -Check { (git config --includes --global user.email) -and (git config --includes --global user.name) } `
    -Fix "git config --global user.email ... ; git config --global user.name ..."

Test-Precondition -Name "Developer Mode registry flag set" `
    -Check {
        (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -Name AllowDevelopmentWithoutDevLicense -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense -eq 1
    } `
    -Fix "Settings > System > For developers > Developer Mode = On"

# Behavioural test. The flag above can be set but not yet in effect until reboot.
Test-Precondition -Name "Symlink creation works unelevated" `
    -Check {
        $src = Join-Path $env:TEMP "dotfiles-symtest-src.tmp"
        $lnk = Join-Path $env:TEMP "dotfiles-symtest-lnk.tmp"
        Remove-Item $lnk -Force -ErrorAction SilentlyContinue
        Set-Content -Path $src -Value "t" -Force
        try {
            New-Item -ItemType SymbolicLink -Path $lnk -Target $src -Force -ErrorAction Stop | Out-Null
            $result = (Get-Item $lnk -Force).LinkType -eq "SymbolicLink"
        } catch { $result = $false }
        Remove-Item $lnk, $src -Force -ErrorAction SilentlyContinue
        $result
    } `
    -Fix "Enable Developer Mode, then REBOOT. The flag alone is not enough."

Test-Precondition -Name "Long path support (OS)" `
    -Check {
        (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled -eq 1
    } `
    -Fix "Elevated: New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force"

Test-Precondition -Name "Long path support (git)" `
    -Check { (git config --system core.longpaths) -eq "true" } `
    -Fix "Elevated: git config --system core.longpaths true"

Test-Precondition -Name "Windows Terminal installed" `
    -Check { $null -ne (Get-Command wt -ErrorAction SilentlyContinue) } `
    -Fix "winget install --id Microsoft.WindowsTerminal -e" `
    -AsWarning

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host "  [INFO] Session elevated: $isAdmin" -ForegroundColor DarkGray
if ($isAdmin) {
    Write-Host "  [INFO] setup.ps1 is designed to run UNELEVATED. Elevation is only needed for preconditions." -ForegroundColor DarkGray
}

Write-Host ""

if ($script:Warnings.Count -gt 0) {
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($w in $script:Warnings) {
        Write-Host "  - $($w.Name)" -ForegroundColor Yellow
        Write-Host "      fix: $($w.Fix)" -ForegroundColor DarkGray
    }
    Write-Host ""
}

if ($script:Failures.Count -gt 0) {
    Write-Host "Preconditions not met ($($script:Failures.Count)):" -ForegroundColor Red
    foreach ($f in $script:Failures) {
        Write-Host "  - $($f.Name)" -ForegroundColor Red
        Write-Host "      fix: $($f.Fix)" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "See PRECONDITIONS.md for the full walkthrough." -ForegroundColor Red
    exit 1
}

Write-Host "All preconditions met. Run .\setup.ps1" -ForegroundColor Green
exit 0
