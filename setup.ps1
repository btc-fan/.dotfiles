#Requires -Version 7.0
<#
.SYNOPSIS
    Autonomous Windows development environment setup.
.DESCRIPTION
    Installs and configures everything defined in packages/. Every stage is
    idempotent and safe to re-run. Nothing aborts the run: failures are
    collected and reported in the summary.

    Runs unelevated. The only stage that needs admin is WSL2, which spawns a
    single elevated child process and prompts via UAC.
.PARAMETER SkipPreflight
    Skip the bootstrap.ps1 precondition check.
.PARAMETER SkipSelfUpdate
    Do not update winget sources, installed packages, or Scoop first.
.PARAMETER SkipPackages
    Do not install winget or Scoop packages.
.PARAMETER SkipVisualStudio
    Do not install Visual Studio. It is a large, slow install.
.PARAMETER SkipRuntimes
    Do not install or configure Python and Node toolchains.
.PARAMETER SkipWsl
    Do not provision WSL2.
.PARAMETER SkipLinks
    Do not symlink configuration files.
.PARAMETER SkipTerminal
    Do not patch Windows Terminal settings.
.EXAMPLE
    .\setup.ps1
.EXAMPLE
    .\setup.ps1 -SkipVisualStudio -SkipWsl
#>
[CmdletBinding()]
param(
    [switch]$SkipPreflight,
    [switch]$SkipSelfUpdate,
    [switch]$SkipPackages,
    [switch]$SkipVisualStudio,
    [switch]$SkipRuntimes,
    [switch]$SkipWsl,
    [switch]$SkipLinks,
    [switch]$SkipTerminal
)

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"
$RepoRoot = $PSScriptRoot

. (Join-Path $RepoRoot "lib\common.ps1")
. (Join-Path $RepoRoot "lib\link.ps1")

$started = Get-Date

Write-Host ""
Write-Host "Windows dotfiles setup" -ForegroundColor Magenta
Write-Host "  repo:     $RepoRoot" -ForegroundColor DarkGray
Write-Host "  elevated: $(Test-Elevated)" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 0. preflight
if (-not $SkipPreflight) {
    Write-Stage "Preflight"
    $bootstrap = Join-Path $RepoRoot "bootstrap.ps1"
    if (Test-Path $bootstrap) {
        & $bootstrap
        if ($LASTEXITCODE -ne 0) {
            Write-Host "`nAborted. Fix the preconditions above and re-run." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Note "bootstrap.ps1 missing"
    }
}

# ---------------------------------------------------------------- 1. self-update
if (-not $SkipSelfUpdate) {
    Write-Stage "Updating the toolchain itself"

    winget source update 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "winget sources" } else { Write-Fail "winget source update" }

    Write-Host "  upgrading installed winget packages..." -ForegroundColor DarkGray
    winget upgrade --all --include-unknown --silent `
        --accept-package-agreements --accept-source-agreements `
        --disable-interactivity 2>&1 | Out-Null
    Write-Ok "winget upgrade --all"

    if (Test-Cmd scoop) {
        scoop update *>$null
        if ($LASTEXITCODE -eq 0) { Write-Ok "scoop itself" } else { Write-Note "scoop update returned $LASTEXITCODE" }
    }
    Update-SessionPath
}

# ---------------------------------------------------------------- 2. winget packages
if (-not $SkipPackages) {
    Write-Stage "winget packages"

    $manifest = Read-Manifest (Join-Path $RepoRoot "packages\winget.txt")
    Write-Host "  $($manifest.Count) queued" -ForegroundColor DarkGray

    $installed = (winget list --accept-source-agreements 2>$null | Out-String)

    foreach ($id in $manifest) {
        if ($installed -match [regex]::Escape($id)) {
            Write-Skip "$id present"
            continue
        }
        Write-Host "  installing $id ..." -ForegroundColor DarkGray
        winget install --id $id --exact --silent --source winget `
            --accept-package-agreements --accept-source-agreements `
            --disable-interactivity 2>&1 | Out-Null

        switch ($LASTEXITCODE) {
            0           { Write-Ok $id }
            -1978335189 { Write-Skip "$id already up to date" }
            default     { Write-Fail "$id (exit $LASTEXITCODE). Verify with: winget search $id" }
        }
    }
    Update-SessionPath
}

# ---------------------------------------------------------------- 3. Visual Studio
if (-not $SkipVisualStudio) {
    Write-Stage "Visual Studio 2026 Community"

    $vsId = "Microsoft.VisualStudio.Community"
    $vsInstalled = (winget list --id $vsId --exact 2>$null | Out-String) -match [regex]::Escape($vsId)

    if ($vsInstalled) {
        Write-Skip "Visual Studio already installed. Modify workloads via the Visual Studio Installer."
    } else {
        $workloads = Read-Manifest (Join-Path $RepoRoot "packages\visualstudio.txt")
        if ($workloads.Count -eq 0) {
            Write-Note "packages/visualstudio.txt is empty, installing core only"
            $override = "--quiet --wait --norestart"
        } else {
            $addArgs  = ($workloads | ForEach-Object { "--add $_" }) -join " "
            $override = "--quiet --wait --norestart --includeRecommended $addArgs"
        }

        Write-Host "  this takes 20-40 minutes and downloads several GB" -ForegroundColor DarkGray
        Write-Host "  workloads: $($workloads.Count)" -ForegroundColor DarkGray

        winget install --id $vsId --exact --source winget `
            --accept-package-agreements --accept-source-agreements `
            --override $override 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) { Write-Ok "Visual Studio 2026 Community" }
        else { Write-Fail "Visual Studio (exit $LASTEXITCODE)" }
    }
}

# ---------------------------------------------------------------- 4. Scoop
if (-not $SkipPackages) {
    Write-Stage "Scoop buckets and packages"

    if (-not (Test-Cmd scoop)) {
        Write-Fail "scoop not found"
    } else {
        $haveBuckets = (scoop bucket list | Select-Object -ExpandProperty Name)
        foreach ($b in @("extras","nerd-fonts","versions")) {
            if ($haveBuckets -contains $b) { Write-Skip "bucket $b"; continue }
            scoop bucket add $b *>$null
            if ($LASTEXITCODE -eq 0) { Write-Ok "bucket $b" } else { Write-Fail "bucket $b" }
        }

        $haveApps = (scoop list 2>$null | Select-Object -ExpandProperty Name)
        foreach ($app in (Read-Manifest (Join-Path $RepoRoot "packages\scoop.txt"))) {
            $name = ($app -split "/")[-1]
            if ($haveApps -contains $name) { Write-Skip "$name present"; continue }
            scoop install $app *>$null
            if ($LASTEXITCODE -eq 0) { Write-Ok $app } else { Write-Fail "scoop: $app" }
        }
        Update-SessionPath
    }
}

# ---------------------------------------------------------------- 5. runtimes
if (-not $SkipRuntimes) {

    # ----- Python via pyenv-win -----
    Write-Stage "Python (pyenv-win)"
    if (Test-Cmd pyenv) {
        pyenv update *>$null

        $available = pyenv install -l 2>$null |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -match "^3\.\d+\.\d+$" }

        $latest = $available |
            Sort-Object { [version]$_ } |
            Select-Object -Last 1

        if (-not $latest) {
            Write-Fail "could not determine latest Python from pyenv"
        } else {
            $have = (pyenv versions 2>$null | Out-String)
            if ($have -match [regex]::Escape($latest)) {
                Write-Skip "Python $latest present"
            } else {
                Write-Host "  installing Python $latest ..." -ForegroundColor DarkGray
                pyenv install $latest *>$null
                if ($LASTEXITCODE -eq 0) { Write-Ok "Python $latest" } else { Write-Fail "pyenv install $latest" }
            }
            pyenv global $latest *>$null
            pyenv rehash *>$null
            Write-Ok "pyenv global -> $latest"
        }
    } else {
        Write-Fail "pyenv not on PATH. Restart the shell and re-run with -SkipPackages"
    }

    # ----- Python via uv -----
    Write-Stage "Python (uv)"
    if (Test-Cmd uv) {
        uv python install 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok "uv managed Python" } else { Write-Fail "uv python install" }

        foreach ($tool in @("ruff","pre-commit")) {
            uv tool install $tool 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "uv tool: $tool" } else { Write-Note "uv tool $tool" }
        }
    } else {
        Write-Fail "uv not on PATH"
    }

    # ----- Node via fnm -----
    Write-Stage "Node (fnm)"
    if (Test-Cmd fnm) {
        fnm install --lts 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok "Node LTS" } else { Write-Fail "fnm install --lts" }

        fnm default lts-latest 2>&1 | Out-Null
        Write-Ok "fnm default -> lts-latest"

        fnm env --use-on-cd --shell power-shell | Out-String | Invoke-Expression
    } else {
        Write-Fail "fnm not on PATH"
    }

    # ----- Azure CLI extensions -----
    Write-Stage "Azure CLI extensions"
    if (Test-Cmd az) {
        $have = (az extension list --output tsv --query "[].name" 2>$null)
        foreach ($ext in @("azure-devops")) {
            if ($have -contains $ext) { Write-Skip "az extension $ext"; continue }
            az extension add --name $ext --only-show-errors 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "az extension $ext" } else { Write-Fail "az extension $ext" }
        }
    } else {
        Write-Note "az not on PATH yet. Restart the shell and re-run."
    }
}

# ---------------------------------------------------------------- 6. config links
if (-not $SkipLinks) {
    Write-Stage "Configuration"

    # Identity is extracted to an untracked local file BEFORE the tracked
    # gitconfig is linked over ~/.gitconfig, so it survives.
    $localGitconfig = Join-Path $RepoRoot "git\.gitconfig.local"
    if (-not (Test-Path $localGitconfig)) {
        $name  = git config --global user.name
        $email = git config --global user.email
        if ($name -and $email) {
            @(
                "# Untracked. Machine-local git identity, pulled in by the tracked .gitconfig."
                "[user]"
                "`tname = $name"
                "`temail = $email"
            ) | Set-Content -LiteralPath $localGitconfig -Encoding utf8
            Write-Ok "extracted git identity -> git/.gitconfig.local"
        } else {
            Write-Note "no global git identity found. Set it, then re-run."
        }
    } else {
        Write-Skip "git/.gitconfig.local exists"
    }

    $links = @(
        @{ Source = "git\.gitconfig";       Target = "$HOME\.gitconfig" }
        @{ Source = "git\.gitconfig.local"; Target = "$HOME\.gitconfig.local" }
        @{ Source = "powershell\Microsoft.PowerShell_profile.ps1"; Target = $PROFILE.CurrentUserCurrentHost }
    )

    foreach ($l in $links) {
        $src = Join-Path $RepoRoot $l.Source
        if (-not (Test-Path $src)) { Write-Skip "$($l.Source) not present"; continue }
        try { New-DotfileLink -Source $src -Target $l.Target }
        catch { Write-Fail "link $($l.Source): $($_.Exception.Message)" }
    }
}

# ---------------------------------------------------------------- 7. PS modules
Write-Stage "PowerShell modules"
foreach ($mod in @("PSReadLine","Terminal-Icons")) {
    if (Get-Module -ListAvailable -Name $mod) { Write-Skip "$mod present"; continue }
    try {
        Install-Module -Name $mod -Scope CurrentUser -Force -AllowClobber -AcceptLicense -ErrorAction Stop
        Write-Ok $mod
    } catch {
        Write-Fail "module $mod : $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------- 8. Terminal
if (-not $SkipTerminal) {
    Write-Stage "Windows Terminal"
    $patch = Join-Path $RepoRoot "terminal\patch-settings.ps1"
    if (Test-Path $patch) { & $patch } else { Write-Note "terminal\patch-settings.ps1 missing" }
}

# ---------------------------------------------------------------- 9. WSL2
if (-not $SkipWsl) {
    Write-Stage "WSL2"

    $distros = ""
    if (Test-Cmd wsl) { $distros = (wsl --list --quiet 2>$null | Out-String) -replace "`0","" }

    if ($distros -match "Ubuntu") {
        Write-Skip "Ubuntu already provisioned"
        wsl --set-default-version 2 2>&1 | Out-Null
    }
    elseif (Test-Elevated) {
        wsl --install -d Ubuntu --no-launch 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok "Ubuntu installed. Launch it once to create your user." }
        else { Write-Fail "wsl --install (exit $LASTEXITCODE). A reboot may be required." }
    }
    else {
        Write-Host "  WSL2 needs elevation. Requesting it for this stage only..." -ForegroundColor DarkGray
        try {
            $p = Start-Process pwsh -Verb RunAs -Wait -PassThru -ArgumentList `
                "-NoProfile","-Command","wsl --install -d Ubuntu --no-launch; wsl --set-default-version 2"
            if ($p.ExitCode -eq 0) { Write-Ok "Ubuntu installed via elevated child process" }
            else { Write-Fail "elevated WSL install returned $($p.ExitCode)" }
        } catch {
            Write-Fail "WSL install declined or failed: $($_.Exception.Message)"
        }
    }
}

# ---------------------------------------------------------------- summary
$elapsed = (Get-Date) - $started
$issues  = Get-Issues

Write-Host ""
Write-Host ("Finished in {0:mm}m {0:ss}s" -f $elapsed) -ForegroundColor Magenta

if ($issues.Count -gt 0) {
    Write-Host "`n$($issues.Count) issue(s):" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
} else {
    Write-Host "No issues." -ForegroundColor Green
}

Update-SessionPath
Write-Host "`nVersions:" -ForegroundColor Cyan
$versions = [ordered]@{
    "PowerShell" = $PSVersionTable.PSVersion.ToString()
    "winget"     = (winget --version 2>$null)
    "git"        = (git --version 2>$null)
    "delta"      = (delta --version 2>$null)
    "pyenv"      = (pyenv --version 2>$null)
    "python"     = (python --version 2>$null)
    "uv"         = (uv --version 2>$null)
    "fnm"        = (fnm --version 2>$null)
    "node"       = (node --version 2>$null)
    "dotnet"     = (dotnet --version 2>$null)
    "az"         = (az version --query '"azure-cli"' -o tsv 2>$null)
    "docker"     = (docker --version 2>$null)
}
$versions.GetEnumerator() | ForEach-Object {
    $v = if ($_.Value) { ($_.Value | Select-Object -First 1) } else { "not found" }
    Write-Host ("  {0,-11} {1}" -f $_.Key, $v)
}

Write-Host "`nNext:" -ForegroundColor Cyan
Write-Host "  - restart Windows Terminal to load the profile"
Write-Host "  - launch Ubuntu once from the Start menu to create your WSL user"
Write-Host "  - sign in to Docker Desktop, Bitwarden, Tailscale, Teams"
Write-Host "  - run .\update.ps1 periodically to keep everything current"
Write-Host ""
