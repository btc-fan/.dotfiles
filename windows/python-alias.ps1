<#
.SYNOPSIS
    Disables the Windows Store Python app execution aliases.
.DESCRIPTION
    Windows ships zero-byte stub executables at
    %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe (and python3.exe) that open
    the Microsoft Store instead of running Python. That directory sits early on
    PATH, so the stubs shadow pyenv and uv: `python --version` prints a Store
    advert rather than a version.

    Settings > Apps > Advanced app settings > App execution aliases toggles
    these. This script does the same thing without the GUI.

    Two layers, because either alone can be undone:
      1. Registry state under the App Paths alias key, which is what the
         Settings toggle actually writes
      2. Renaming the stub files, which takes effect immediately in new shells

    Only the Python stubs are touched. Other aliases are left alone.
.PARAMETER Status
    Report current state. Read-only.
.PARAMETER Disable
    Disable the Python aliases.
.PARAMETER Enable
    Restore them.
.EXAMPLE
    .\windows\python-alias.ps1 -Status
    .\windows\python-alias.ps1 -Disable
#>
[CmdletBinding(DefaultParameterSetName = "Status")]
param(
    [Parameter(ParameterSetName = "Status")][switch]$Status,
    [Parameter(ParameterSetName = "Disable")][switch]$Disable,
    [Parameter(ParameterSetName = "Enable")][switch]$Enable
)

$appsDir = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$stubs   = @("python.exe", "python3.exe")
$regRoot = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"

function Get-StubState {
    foreach ($s in $stubs) {
        $live     = Join-Path $appsDir $s
        $disabled = "$live.dotfiles-disabled"
        $isStub   = $false

        if (Test-Path $live) {
            $item = Get-Item $live -Force -ErrorAction SilentlyContinue
            # Real interpreters have size. The Store stubs are zero bytes.
            $isStub = ($item.Length -eq 0)
        }

        [pscustomobject]@{
            Name        = $s
            StubPresent = (Test-Path $live) -and $isStub
            RealPresent = (Test-Path $live) -and (-not $isStub)
            Renamed     = Test-Path $disabled
        }
    }
}

function Show-State {
    Write-Host "`nStore Python execution aliases" -ForegroundColor Cyan
    foreach ($s in (Get-StubState)) {
        if ($s.StubPresent) {
            Write-Host ("  {0,-14} ACTIVE  (shadows pyenv and uv)" -f $s.Name) -ForegroundColor Yellow
        } elseif ($s.Renamed) {
            Write-Host ("  {0,-14} disabled" -f $s.Name) -ForegroundColor Green
        } elseif ($s.RealPresent) {
            Write-Host ("  {0,-14} real executable, not a stub, left alone" -f $s.Name) -ForegroundColor DarkGray
        } else {
            Write-Host ("  {0,-14} not present" -f $s.Name) -ForegroundColor DarkGray
        }
    }

    $resolved = (Get-Command python -ErrorAction SilentlyContinue).Source
    Write-Host "`n  python resolves to: $(if ($resolved) { $resolved } else { 'nothing on PATH' })" -ForegroundColor Gray
    Write-Host ""
}

if ($PSCmdlet.ParameterSetName -eq "Status" -or (-not $Disable -and -not $Enable)) {
    Show-State
    Write-Host "Disable with: .\windows\python-alias.ps1 -Disable`n" -ForegroundColor DarkGray
    return
}

if ($Disable) {
    Write-Host "`nDisabling Store Python aliases" -ForegroundColor Cyan
    $changed = 0

    foreach ($s in (Get-StubState)) {
        $live     = Join-Path $appsDir $s.Name
        $disabled = "$live.dotfiles-disabled"

        if ($s.RealPresent) {
            Write-Host "  [SKIP] $($s.Name) is a real executable, not touching it" -ForegroundColor DarkGray
            continue
        }
        if ($s.Renamed) {
            Write-Host "  [SKIP] $($s.Name) already disabled" -ForegroundColor DarkGray
            continue
        }
        if (-not $s.StubPresent) {
            Write-Host "  [SKIP] $($s.Name) not present" -ForegroundColor DarkGray
            continue
        }

        try {
            Move-Item -LiteralPath $live -Destination $disabled -Force -ErrorAction Stop
            Write-Host "  [OK]   $($s.Name) renamed" -ForegroundColor Green
            $changed++
        } catch {
            Write-Host "  [FAIL] $($s.Name): $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "         Turn it off manually: Settings > Apps > Advanced app settings > App execution aliases" -ForegroundColor DarkGray
        }
    }

    # Registry layer, so the Settings toggle reflects reality
    try {
        foreach ($s in $stubs) {
            $key = Join-Path $regRoot $s
            if (Test-Path $key) {
                Set-ItemProperty -Path $key -Name "(Default)" -Value "" -ErrorAction SilentlyContinue
            }
        }
    } catch { }

    if ($changed -gt 0) {
        Write-Host "`n  Restart your shell for PATH resolution to update." -ForegroundColor DarkGray
    }
    Show-State
}

if ($Enable) {
    Write-Host "`nRestoring Store Python aliases" -ForegroundColor Cyan
    foreach ($s in $stubs) {
        $live     = Join-Path $appsDir $s
        $disabled = "$live.dotfiles-disabled"
        if (Test-Path $disabled) {
            Move-Item -LiteralPath $disabled -Destination $live -Force
            Write-Host "  [OK]   $s restored" -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] $s was not disabled by this script" -ForegroundColor DarkGray
        }
    }
    Show-State
}