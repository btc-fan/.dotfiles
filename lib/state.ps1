# Install state tracking. Prevents redundant reinstalls and stops a broken
# package ID from being retried on every single run forever.
#
# State lives in .setup-state.json at the repo root (gitignored).
#
# Status values:
#   installed   verified present, always skipped
#   failed      attempt failed, retried until MaxAttempts
#   quarantined attempts exhausted, skipped unless -RetryFailed

$script:StatePath  = $null
$script:StateData  = $null
$script:MaxAttempts = 2

function Initialize-SetupState {
    param([Parameter(Mandatory)][string]$RepoRoot)

    $script:StatePath = Join-Path $RepoRoot ".setup-state.json"

    if (Test-Path $script:StatePath) {
        try {
            $raw = Get-Content $script:StatePath -Raw | ConvertFrom-Json
            $script:StateData = @{}
            foreach ($p in $raw.packages.PSObject.Properties) {
                $script:StateData[$p.Name] = @{
                    status      = $p.Value.status
                    attempts    = [int]$p.Value.attempts
                    lastAttempt = $p.Value.lastAttempt
                    lastError   = $p.Value.lastError
                }
            }
            return
        } catch {
            Write-Host "  [WARN] state file unreadable, starting fresh" -ForegroundColor Yellow
        }
    }
    $script:StateData = @{}
}

function Get-PackageState {
    param([Parameter(Mandatory)][string]$Key)
    if ($script:StateData.ContainsKey($Key)) { return $script:StateData[$Key] }
    return @{ status = "unknown"; attempts = 0; lastAttempt = $null; lastError = $null }
}

function Set-PackageState {
    param(
        [Parameter(Mandatory)][string]$Key,
        [Parameter(Mandatory)][ValidateSet("installed","failed","quarantined")][string]$Status,
        [string]$ErrorText
    )

    $existing = Get-PackageState -Key $Key
    $attempts = if ($Status -eq "installed") { $existing.attempts } else { $existing.attempts + 1 }

    if ($Status -eq "failed" -and $attempts -ge $script:MaxAttempts) {
        $Status = "quarantined"
    }

    $script:StateData[$Key] = @{
        status      = $Status
        attempts    = $attempts
        lastAttempt = (Get-Date).ToString("o")
        lastError   = $ErrorText
    }
    return $Status
}

# Returns: Install, Skip, or Quarantined
function Get-PackageAction {
    param(
        [Parameter(Mandatory)][string]$Key,
        [bool]$PresentOnSystem = $false,
        [switch]$RetryFailed
    )

    if ($PresentOnSystem) {
        Set-PackageState -Key $Key -Status "installed" | Out-Null
        return "Skip"
    }

    $state = Get-PackageState -Key $Key

    switch ($state.status) {
        "installed" {
            # Recorded installed but not found on the system: it was removed.
            return "Install"
        }
        "quarantined" {
            if ($RetryFailed) { return "Install" }
            return "Quarantined"
        }
        default { return "Install" }
    }
}

function Save-SetupState {
    if (-not $script:StatePath) { return }
    $out = [ordered]@{
        version  = 1
        updated  = (Get-Date).ToString("o")
        packages = $script:StateData
    }
    $out | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $script:StatePath -Encoding utf8
}

function Get-QuarantinedPackages {
    $script:StateData.GetEnumerator() |
        Where-Object { $_.Value.status -eq "quarantined" } |
        ForEach-Object { [pscustomobject]@{ Package = $_.Key; Attempts = $_.Value.attempts; Error = $_.Value.lastError } }
}

function Clear-SetupState {
    if ($script:StatePath -and (Test-Path $script:StatePath)) {
        Remove-Item $script:StatePath -Force
    }
    $script:StateData = @{}
}
