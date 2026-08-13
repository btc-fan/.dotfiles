<#
.SYNOPSIS
    GNU stow replacement. Symlinks a repo file to where an application expects it.
.DESCRIPTION
    Idempotent and non-destructive:
      - already linked to the same source  -> no-op
      - linked elsewhere                   -> relinked
      - real file or directory in the way  -> backed up, then linked
    Requires Developer Mode, or an elevated session.
#>

function New-DotfileLink {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Target
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Source not found: $Source"
    }
    $Source = (Resolve-Path -LiteralPath $Source).Path

    $parent = Split-Path -Parent $Target
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $existing = Get-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue

    if ($existing) {
        if ($existing.LinkType -eq "SymbolicLink") {
            $current = $existing.Target
            if ($current) {
                $resolved = (Resolve-Path -LiteralPath $current -ErrorAction SilentlyContinue).Path
                if ($resolved -eq $Source) {
                    Write-Host "  [SKIP] linked already: $Target" -ForegroundColor DarkGray
                    return
                }
            }
            Remove-Item -LiteralPath $Target -Force
        }
        else {
            $backup = "$Target.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Move-Item -LiteralPath $Target -Destination $backup -Force
            Write-Host "  [BACKUP] $Target -> $backup" -ForegroundColor Yellow
        }
    }

    New-Item -ItemType SymbolicLink -Path $Target -Target $Source -Force | Out-Null
    Write-Host "  [LINK] $Target -> $Source" -ForegroundColor Green
}

function Remove-DotfileLink {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Target)

    $item = Get-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -eq "SymbolicLink") {
        Remove-Item -LiteralPath $Target -Force
        Write-Host "  [UNLINK] $Target" -ForegroundColor Yellow
    }
}
