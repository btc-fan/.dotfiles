<#
.SYNOPSIS
    Rebuilds pyenv-win's version cache. Replaces the broken `pyenv update`.
.DESCRIPTION
    pyenv-win's updater (libexec/pyenv-update.vbs) parses python.org HTML using
    the `htmlfile` COM object, which is deprecated and fails on Windows 11 with
    "This command is not supported". The version cache therefore never updates
    and stays frozen around 3.11.0b4 from 2022, so `pyenv install -l` cannot
    see any modern Python.

    Upstream issues 715 and 725 are open; fixing PRs 717 and 729 are unmerged.

    This script does the same job with Invoke-WebRequest and regex, writing the
    same .versions_cache.xml schema pyenv-win expects:

      <version x64="true" webInstall="false" msi="false">
        <code>3.13.7</code>
        <file>python-3.13.7-amd64.exe</file>
        <URL>https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe</URL>
      </version>

    Only stable CPython 3.x releases are emitted. Pre-releases (a, b, rc) are
    skipped: this feeds an automated "install latest" step, and betas are not
    what you want as a default interpreter.

    Existence of each installer is verified with a HEAD request, so the cache
    never advertises a download that 404s.
.PARAMETER MinVersion
    Oldest minor version to include. Default 3.9. Lower means a slower run.
.PARAMETER Quiet
    Suppress progress output.
.EXAMPLE
    .\lib\pyenv-update.ps1
    .\lib\pyenv-update.ps1 -MinVersion 3.11
#>
[CmdletBinding()]
param(
    [string]$MinVersion = "3.9",
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

function Say { param($m, $c = "Gray") if (-not $Quiet) { Write-Host $m -ForegroundColor $c } }

# ---------- locate pyenv ----------
$pyenvRoot = $env:PYENV_ROOT
if (-not $pyenvRoot) {
    foreach ($cand in @("$HOME\scoop\apps\pyenv\current\pyenv-win", "$HOME\.pyenv\pyenv-win")) {
        if (Test-Path $cand) { $pyenvRoot = $cand; break }
    }
}
if (-not $pyenvRoot -or -not (Test-Path $pyenvRoot)) {
    Write-Host "  [FAIL] pyenv root not found. Is pyenv installed?" -ForegroundColor Red
    exit 1
}
$pyenvRoot = $pyenvRoot.TrimEnd("\")
$cachePath = Join-Path $pyenvRoot ".versions_cache.xml"

Say "  pyenv root: $pyenvRoot" "DarkGray"

# ---------- fetch the release index ----------
$indexUrl = "https://www.python.org/ftp/python/"
Say "  fetching $indexUrl ..." "DarkGray"

try {
    $index = Invoke-WebRequest -Uri $indexUrl -UseBasicParsing -TimeoutSec 30
} catch {
    Write-Host "  [FAIL] could not reach python.org: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$minV = [version]"$MinVersion.0"

# Directory listing entries look like: href="3.13.7/"
$versions = [regex]::Matches($index.Content, 'href="(\d+\.\d+\.\d+)/"') |
    ForEach-Object { $_.Groups[1].Value } |
    Where-Object { $_ -like "3.*" } |
    Sort-Object -Unique |
    Where-Object {
        try { [version]$_ -ge $minV } catch { $false }
    } |
    Sort-Object { [version]$_ }

if ($versions.Count -eq 0) {
    Write-Host "  [FAIL] no versions parsed from the index" -ForegroundColor Red
    exit 1
}

Say "  $($versions.Count) candidate release(s) at or above $MinVersion" "DarkGray"

# ---------- verify installers exist ----------
$entries = [System.Collections.Generic.List[string]]::new()
$found   = 0
$i       = 0

foreach ($v in $versions) {
    $i++
    if (-not $Quiet -and ($i % 10 -eq 0)) {
        Write-Host "`r  checking $i/$($versions.Count) ..." -NoNewline -ForegroundColor DarkGray
    }

    foreach ($arch in @(
        @{ Suffix = "-amd64"; X64 = "true"  }
        @{ Suffix = "";       X64 = "false" }
    )) {
        $file = "python-$v$($arch.Suffix).exe"
        $url  = "https://www.python.org/ftp/python/$v/$file"

        $ok = $false
        try {
            $r = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 10
            $ok = ($r.StatusCode -eq 200)
        } catch { $ok = $false }

        if (-not $ok) { continue }

        # pyenv-win uses a bare version code for x64 and a -win32 suffix for x86
        $code = if ($arch.X64 -eq "true") { $v } else { "$v-win32" }

        $entries.Add(@"
<version x64="$($arch.X64)" webInstall="false" msi="false">
<code>$code</code>
<file>$file</file>
<URL>$url</URL>
</version>
"@)
        $found++
    }
}

if (-not $Quiet) { Write-Host "`r" -NoNewline }

if ($found -eq 0) {
    Write-Host "  [FAIL] no installers verified. Not overwriting the cache." -ForegroundColor Red
    exit 1
}

# ---------- write the cache ----------
if (Test-Path $cachePath) {
    $backup = "$cachePath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $cachePath $backup -Force
    Say "  backup: $(Split-Path $backup -Leaf)" "DarkGray"
}

$xml = @"
<?xml version="1.0" encoding="utf-8" standalone="no"?>
<versions>
$($entries -join "`n")
</versions>
"@

[System.IO.File]::WriteAllText($cachePath, $xml, (New-Object System.Text.UTF8Encoding $false))

$latest = $versions | Select-Object -Last 1
Say "  [OK]   cache rebuilt: $found installer(s), latest stable $latest" "Green"

# hand the latest version back to the caller
$latest