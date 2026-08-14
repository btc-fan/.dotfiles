<#
.SYNOPSIS
    Installs the winget manifest in a single elevated process.
.DESCRIPTION
    Machine-scope installers (Docker Desktop, .NET SDK, Visual Studio and
    others) each trigger their own UAC prompt when winget runs unelevated.
    That turns an unattended setup into twenty minutes of clicking Yes.

    UAC cannot be auto-accepted from an unelevated process. That is the whole
    point of UAC: if a script could click Yes on your behalf, it would provide
    no protection at all. The only honest fix is to consolidate the prompts
    into one.

    setup.ps1 launches this script via Start-Process -Verb RunAs, producing a
    single UAC prompt. Every winget install then runs inside that elevated
    context with no further prompts.

    Results are written to a JSON file that the parent process reads back, so
    install state survives the process boundary.

    Scoop is deliberately NOT handled here. It is designed for user scope and
    misbehaves when run as administrator.
.PARAMETER RepoRoot
    Path to the dotfiles repo.
.PARAMETER ResultPath
    Where to write the results JSON for the parent process.
.PARAMETER IncludeVisualStudio
    Also install Visual Studio with its workload override.
.PARAMETER RetryFailed
    Attempt packages previously marked quarantined.
.NOTES
    Not intended to be run directly. setup.ps1 invokes it.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RepoRoot,
    [Parameter(Mandatory)][string]$ResultPath,
    [switch]$IncludeVisualStudio,
    [switch]$RetryFailed
)

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

. (Join-Path $RepoRoot "lib\common.ps1")
. (Join-Path $RepoRoot "lib\state.ps1")

Initialize-SetupState -RepoRoot $RepoRoot

$results = @{}

Write-Host ""
Write-Host "Elevated package installation" -ForegroundColor Magenta
Write-Host "  This window handles installers that need administrator rights." -ForegroundColor DarkGray
Write-Host "  It closes automatically when finished." -ForegroundColor DarkGray

# ---------------------------------------------------------------- winget
Write-Stage "winget packages"

$manifest = Read-Manifest (Join-Path $RepoRoot "packages\winget.txt")

# Per-package installer overrides for packages whose manifest lacks a working
# silent switch. See packages/overrides.txt for why this is necessary.
$overrides = @{}
$ovFile = Join-Path $RepoRoot "packages\overrides.txt"
if (Test-Path $ovFile) {
    foreach ($line in (Read-Manifest $ovFile)) {
        if ($line -match "^\s*([^=]+?)\s*=\s*(.+)$") {
            $overrides[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
    if ($overrides.Count -gt 0) { Write-Host "  $($overrides.Count) override(s) loaded" -ForegroundColor DarkGray }
}
$listing  = (winget list --accept-source-agreements 2>$null | Out-String)
Write-Host "  $($manifest.Count) in manifest" -ForegroundColor DarkGray

foreach ($id in $manifest) {
    $key     = "winget:$id"
    $present = $listing -match [regex]::Escape($id)
    $action  = Get-PackageAction -Key $key -PresentOnSystem $present -RetryFailed:$RetryFailed

    if ($action -eq "Skip") {
        Write-Skip "$id present"
        $results[$key] = @{ status = "installed"; error = $null }
        continue
    }
    if ($action -eq "Quarantined") {
        $s = Get-PackageState -Key $key
        Write-Skip "$id quarantined after $($s.attempts) attempts"
        continue
    }

    Write-Host "  installing $id ..." -ForegroundColor DarkGray
    if ($overrides.ContainsKey($id)) {
        Write-Host "    override: $($overrides[$id])" -ForegroundColor DarkGray
        winget install --id $id --exact --source winget `
            --accept-package-agreements --accept-source-agreements `
            --disable-interactivity --override $overrides[$id] 2>&1 | Out-Null
    } else {
        winget install --id $id --exact --silent --source winget `
            --accept-package-agreements --accept-source-agreements `
            --disable-interactivity 2>&1 | Out-Null
    }
    $code = $LASTEXITCODE

    if ($code -eq 0 -or $code -eq -1978335189) {
        Write-Ok $id
        $results[$key] = @{ status = "installed"; error = $null }
    } else {
        Write-Fail "$id (exit $code)"
        $results[$key] = @{ status = "failed"; error = "exit $code" }
    }
}

# ---------------------------------------------------------------- Visual Studio
if ($IncludeVisualStudio) {
    Write-Stage "Visual Studio 2026 Community"

    $vsId    = "Microsoft.VisualStudio.Community"
    $key     = "winget:$vsId"
    $present = (winget list --id $vsId --exact 2>$null | Out-String) -match [regex]::Escape($vsId)
    $action  = Get-PackageAction -Key $key -PresentOnSystem $present -RetryFailed:$RetryFailed

    if ($action -eq "Skip") {
        Write-Skip "installed. Change workloads via the Visual Studio Installer."
        $results[$key] = @{ status = "installed"; error = $null }
    }
    elseif ($action -eq "Quarantined") {
        Write-Skip "quarantined. Use -RetryFailed to retry."
    }
    else {
        $workloads = Read-Manifest (Join-Path $RepoRoot "packages\visualstudio.txt")
        $addArgs   = ($workloads | ForEach-Object { "--add $_" }) -join " "
        $override  = "--quiet --wait --norestart --includeRecommended $addArgs"

        Write-Host "  $($workloads.Count) workloads. This takes 20-40 minutes." -ForegroundColor DarkGray
        Write-Host "  Leave this window open." -ForegroundColor Yellow

        winget install --id $vsId --exact --source winget `
            --accept-package-agreements --accept-source-agreements `
            --override $override 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Visual Studio 2026 Community"
            $results[$key] = @{ status = "installed"; error = $null }
        } else {
            Write-Fail "Visual Studio (exit $LASTEXITCODE)"
            $results[$key] = @{ status = "failed"; error = "exit $LASTEXITCODE" }
        }
    }
}

# ---------------------------------------------------------------- handback
try {
    @{
        completed = (Get-Date).ToString("o")
        packages  = $results
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultPath -Encoding utf8
} catch {
    Write-Host "  [FAIL] could not write results: $($_.Exception.Message)" -ForegroundColor Red
}

$failed = ($results.Values | Where-Object { $_.status -eq "failed" }).Count
Write-Host ""
if ($failed -gt 0) {
    Write-Host "  $failed package(s) failed. Details in the main window." -ForegroundColor Yellow
    Start-Sleep -Seconds 4
} else {
    Write-Host "  All packages handled." -ForegroundColor Green
    Start-Sleep -Seconds 2
}
