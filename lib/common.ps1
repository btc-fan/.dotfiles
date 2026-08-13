# Shared helpers. Dot-sourced by setup.ps1 and update.ps1.

$script:Issues = @()

function Write-Stage { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Skip  { param($m) Write-Host "  [SKIP] $m" -ForegroundColor DarkGray }
function Write-Note  { param($m) Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Write-Fail  {
    param($m)
    $script:Issues += $m
    Write-Host "  [FAIL] $m" -ForegroundColor Red
}
function Get-Issues { $script:Issues }

function Test-Elevated {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Read-Manifest {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @() }
    Get-Content $Path |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith("#") }
}

function Test-Cmd {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

# Refresh PATH from the registry so tools installed in this session are usable
# without restarting the shell.
function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable("Path","Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("Path","User")
    $env:Path = ($machine, $user | Where-Object { $_ }) -join ";"
}
