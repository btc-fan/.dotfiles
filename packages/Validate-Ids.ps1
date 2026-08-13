# Validates that every ID in packages/winget.txt resolves in the winget source.
# Catches casing errors and dead IDs before an install run wastes time on them.
$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $RepoRoot "lib\common.ps1")

$ids = Read-Manifest (Join-Path $RepoRoot "packages\winget.txt")
Write-Host "`nValidating $($ids.Count) winget IDs...`n" -ForegroundColor Cyan

$bad = @()
foreach ($id in $ids) {
    $hit = winget show --id $id --exact --accept-source-agreements 2>&1 | Out-String
    if ($hit -match "No package found") {
        # retry case-insensitively to suggest the correct casing
        $loose = winget search $id --accept-source-agreements 2>&1 | Out-String
        $suggest = ($loose -split "`n" | Where-Object { $_ -match [regex]::Escape($id) } | Select-Object -First 1)
        Write-Host "  [BAD]  $id" -ForegroundColor Red
        if ($suggest) { Write-Host "         did you mean: $($suggest.Trim())" -ForegroundColor Yellow }
        $bad += $id
    } else {
        Write-Host "  [OK]   $id" -ForegroundColor Green
    }
}

Write-Host ""
if ($bad.Count -gt 0) {
    Write-Host "$($bad.Count) invalid ID(s). winget --exact is CASE-SENSITIVE." -ForegroundColor Red
    exit 1
}
Write-Host "All IDs valid." -ForegroundColor Green
