#Requires -Version 7.0
<#
.SYNOPSIS
    Autonomous Windows development environment setup.
.DESCRIPTION
    Installs and configures everything defined in packages/. Idempotent: safe
    to run any number of times. Nothing aborts the run; failures are collected
    and reported in the summary.

    Install state persists in .setup-state.json. A package that fails twice is
    quarantined and skipped on later runs, so a bad ID is not retried forever.
    Use -RetryFailed to give quarantined packages another chance.

    A machine health report runs as a background job during the install and
    prints at the end, so it costs no wall-clock time.

    Runs unelevated. Only the WSL2 stage requests elevation, via a single UAC
    prompt for a child process.
.PARAMETER RetryFailed
    Retry packages that were quarantined after repeated failures.
.PARAMETER ResetState
    Discard install state and treat every package as new.
.EXAMPLE
    .\setup.ps1
.EXAMPLE
    .\setup.ps1 -SkipVisualStudio -SkipWsl
.EXAMPLE
    .\setup.ps1 -RetryFailed
#>
[CmdletBinding()]
param(
    [switch]$SkipPreflight,
    [switch]$SelfUpdate,
    [switch]$SkipPackages,
    [switch]$SkipVisualStudio,
    [switch]$SkipRuntimes,
    [switch]$SkipWsl,
    [switch]$SkipLinks,
    [switch]$SkipTerminal,
    [switch]$SkipTweaks,
    [switch]$SkipHealth,
    [switch]$RetryFailed,
    [switch]$ResetState,
    [switch]$NoElevate,
    [switch]$SkipMdmGuard
)

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"
$RepoRoot = $PSScriptRoot

. (Join-Path $RepoRoot "lib\common.ps1")
. (Join-Path $RepoRoot "lib\link.ps1")
. (Join-Path $RepoRoot "lib\state.ps1")
. (Join-Path $RepoRoot "lib\inventory.ps1")

$started = Get-Date

Write-Host ""
Write-Host "Windows dotfiles setup" -ForegroundColor Magenta
Write-Host "  repo:     $RepoRoot" -ForegroundColor DarkGray
Write-Host "  elevated: $(Test-Elevated)" -ForegroundColor DarkGray

Initialize-SetupState -RepoRoot $RepoRoot
if ($ResetState) { Clear-SetupState; Initialize-SetupState -RepoRoot $RepoRoot; Write-Host "  state:    reset" -ForegroundColor DarkGray }

# ---------------------------------------------------------------- health job
$healthJob = $null
if (-not $SkipHealth) {
    $healthScript = Join-Path $RepoRoot "lib\health.ps1"
    if (Test-Path $healthScript) {
        $healthJob = Start-Job -FilePath $healthScript
        Write-Host "  health:   running in background" -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------- 0. preflight
if (-not $SkipPreflight) {
    Write-Stage "Preflight"
    $bootstrap = Join-Path $RepoRoot "bootstrap.ps1"
    if (Test-Path $bootstrap) {
        & $bootstrap
        if ($LASTEXITCODE -ne 0) {
            if ($healthJob) { Stop-Job $healthJob -ErrorAction SilentlyContinue; Remove-Job $healthJob -Force -ErrorAction SilentlyContinue }
            Write-Host "`nAborted. Fix the preconditions above and re-run." -ForegroundColor Red
            exit 1
        }
    } else { Write-Note "bootstrap.ps1 missing" }
}

# ---------------------------------------------------------------- 1. self-update
if ($SelfUpdate) {
    Write-Stage "Updating the toolchain itself"

    winget source update 2>&1 | Out-Null
    Write-Ok "winget sources"

    Write-Host "  upgrading installed winget packages..." -ForegroundColor DarkGray
    winget upgrade --all --include-unknown --silent `
        --accept-package-agreements --accept-source-agreements `
        --disable-interactivity 2>&1 | Out-Null
    Write-Ok "winget upgrade --all"

    if (Test-Cmd scoop) {
        scoop update *>$null
        Write-Ok "scoop"
    }
    Update-SessionPath
}

# ---------------------------------------------------------------- 2. winget packages
# ---------------------------------------------------------------- running apps
# Installers cannot replace files locked by a running process, so they raise
# their own UI asking you to close the app. That is the vendor's installer, not
# winget, so --silent does not suppress it. Warn up front instead of letting it
# block an unattended run halfway through.
if (-not $SkipPackages) {
    $conflicts = @(
        @{ Process = "chrome";   App = "Google Chrome" }
        @{ Process = "ms-teams"; App = "Microsoft Teams" }
        @{ Process = "Teams";    App = "Microsoft Teams" }
        @{ Process = "Docker Desktop"; App = "Docker Desktop" }
        @{ Process = "Telegram"; App = "Telegram" }
        @{ Process = "Discord";  App = "Discord" }
        @{ Process = "Postman";  App = "Postman" }
        @{ Process = "Code";     App = "VS Code" }
    )

    $running = foreach ($c2 in $conflicts) {
        if (Get-Process -Name $c2.Process -ErrorAction SilentlyContinue) { $c2.App }
    }
    $running = $running | Select-Object -Unique

    if ($running) {
        Write-Stage "Running applications"
        Write-Note "these are open and their installers will prompt you to close them:"
        $running | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
        Write-Host "  Close them now for an unattended run, or accept the prompts as they appear." -ForegroundColor DarkGray
        Write-Host "  Continuing in 10 seconds..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 10
    }
}
# ---------------------------------------------------------------- 1a. MDM guard
# Runs BEFORE any package installs. On a fresh machine the winget stage puts
# Teams and Outlook on disk, and signing into either is exactly how a personal
# device gets silently registered and enrolled. Protection has to exist first.
# Windows feature updates re-enable the Automatic-Device-Join task and can clear
# the policy key, so this verifies on every run rather than trusting a one-shot.
if (-not $SkipMdmGuard) {
    Write-Stage "MDM enrollment posture"
    . (Join-Path $RepoRoot "lib\mdm.ps1")

    if (Test-CorporateDevice) {
        Write-Skip "device is Entra or domain joined. Leaving management alone."
    } else {
        $blockState = Get-WorkplaceJoinBlockState
        if ($blockState.RegistryBlocked -and $blockState.TriggersDisabled -and $blockState.MdmRegistrationBlocked) {
            Write-Skip "protection active"
        } else {
            Write-Note "protection has drifted. Re-applying."
            $blockScript = Join-Path $RepoRoot "windows\block-mdm.ps1"
            try {
                $bp = Start-Process pwsh -Verb RunAs -Wait -PassThru -ArgumentList `
                    "-NoProfile","-ExecutionPolicy","Bypass","-File",$blockScript,"-Block"
                if ($bp.ExitCode -eq 0) { Write-Ok "re-applied" } else { Write-Fail "block-mdm returned $($bp.ExitCode)" }
            } catch {
                Write-Note "elevation declined. Run: .\windows\block-mdm.ps1 -Block"
            }
        }
    }
}


$elevationDone = $false
if (-not $SkipPackages -and -not $NoElevate -and -not (Test-Elevated)) {
    Write-Stage "Elevated package installation"
    Write-Host "  Machine-scope installers each raise their own UAC prompt." -ForegroundColor DarkGray
    Write-Host "  Approving once here avoids clicking Yes twenty times." -ForegroundColor DarkGray

    $resultPath = Join-Path $env:TEMP "dotfiles-install-results.json"
    Remove-Item $resultPath -Force -ErrorAction SilentlyContinue

    $childArgs = @(
        "-NoProfile","-ExecutionPolicy","Bypass"
        "-File", (Join-Path $RepoRoot "lib\install-elevated.ps1")
        "-RepoRoot", $RepoRoot
        "-ResultPath", $resultPath
    )
    if (-not $SkipVisualStudio -and -not $elevationDone) { $childArgs += "-IncludeVisualStudio" }
    if ($RetryFailed)           { $childArgs += "-RetryFailed" }

    try {
        $proc = Start-Process pwsh -Verb RunAs -Wait -PassThru -ArgumentList $childArgs
        if (Test-Path $resultPath) {
            $res = Get-Content $resultPath -Raw | ConvertFrom-Json
            foreach ($p in $res.packages.PSObject.Properties) {
                Set-PackageState -Key $p.Name -Status $p.Value.status -ErrorText $p.Value.error | Out-Null
                if ($p.Value.status -eq "failed") { Write-Fail "$($p.Name) ($($p.Value.error))" }
            }
            Save-SetupState
            Write-Ok "elevated stage complete"
            $elevationDone = $true
        } else {
            Write-Note "no results returned. Falling back to unelevated installs."
        }
    } catch {
        Write-Note "elevation declined. Falling back to unelevated installs (expect UAC prompts)."
    }
    Remove-Item $resultPath -Force -ErrorAction SilentlyContinue
}

if (-not $SkipPackages -and -not $elevationDone) {
    Write-Stage "winget packages"

    $manifest  = Read-Manifest (Join-Path $RepoRoot "packages\winget.txt")
    $listing   = (winget list --accept-source-agreements 2>$null | Out-String)
    Write-Host "  $($manifest.Count) in manifest" -ForegroundColor DarkGray

    foreach ($id in $manifest) {
        $key     = "winget:$id"
        $present = $listing -match [regex]::Escape($id)
        $action  = Get-PackageAction -Key $key -PresentOnSystem $present -RetryFailed:$RetryFailed

        if ($action -eq "Skip") { Write-Skip "$id present"; continue }
        if ($action -eq "Quarantined") {
            $s = Get-PackageState -Key $key
            Write-Skip "$id quarantined after $($s.attempts) attempts. Use -RetryFailed to retry."
            continue
        }

        Write-Host "  installing $id ..." -ForegroundColor DarkGray
        $out = winget install --id $id --exact --silent --source winget `
            --accept-package-agreements --accept-source-agreements `
            --disable-interactivity 2>&1 | Out-String
        $code = $LASTEXITCODE

        if ($code -eq 0 -or $code -eq -1978335189) {
            Set-PackageState -Key $key -Status "installed" | Out-Null
            Write-Ok $id
        } else {
            $newStatus = Set-PackageState -Key $key -Status "failed" -ErrorText "exit $code"
            if ($newStatus -eq "quarantined") {
                Write-Fail "$id (exit $code) QUARANTINED. Verify with: winget search $id"
            } else {
                Write-Fail "$id (exit $code), will retry next run"
            }
        }
    }
    Save-SetupState
    Update-SessionPath
}

# ---------------------------------------------------------------- 3. Visual Studio
if (-not $SkipVisualStudio -and -not $elevationDone) {
    Write-Stage "Visual Studio 2026 Community"

    $vsId    = "Microsoft.VisualStudio.Community"
    $key     = "winget:$vsId"
    $present = (winget list --id $vsId --exact 2>$null | Out-String) -match [regex]::Escape($vsId)
    $action  = Get-PackageAction -Key $key -PresentOnSystem $present -RetryFailed:$RetryFailed

    if ($action -eq "Skip") {
        Write-Skip "installed. Change workloads via the Visual Studio Installer."
    }
    elseif ($action -eq "Quarantined") {
        Write-Skip "quarantined. Use -RetryFailed to retry."
    }
    else {
        $workloads = Read-Manifest (Join-Path $RepoRoot "packages\visualstudio.txt")
        $addArgs   = ($workloads | ForEach-Object { "--add $_" }) -join " "
        $override  = "--quiet --wait --norestart --includeRecommended $addArgs"

        Write-Host "  $($workloads.Count) workloads, 20-40 minutes, several GB" -ForegroundColor DarkGray

        winget install --id $vsId --exact --source winget `
            --accept-package-agreements --accept-source-agreements `
            --override $override 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Set-PackageState -Key $key -Status "installed" | Out-Null
            Write-Ok "Visual Studio 2026 Community"
        } else {
            Set-PackageState -Key $key -Status "failed" -ErrorText "exit $LASTEXITCODE" | Out-Null
            Write-Fail "Visual Studio (exit $LASTEXITCODE)"
        }
        Save-SetupState
    }
}

# ---------------------------------------------------------------- 4. Scoop
if (-not $SkipPackages) {
    Write-Stage "Scoop"

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
            $name    = ($app -split "/")[-1]
            $key     = "scoop:$name"
            $present = $haveApps -contains $name
            $action  = Get-PackageAction -Key $key -PresentOnSystem $present -RetryFailed:$RetryFailed

            if ($action -eq "Skip") { Write-Skip "$name present"; continue }
            if ($action -eq "Quarantined") { Write-Skip "$name quarantined. Use -RetryFailed."; continue }

            scoop install $app *>$null
            if ($LASTEXITCODE -eq 0) {
                Set-PackageState -Key $key -Status "installed" | Out-Null
                Write-Ok $app
            } else {
                $s = Set-PackageState -Key $key -Status "failed" -ErrorText "exit $LASTEXITCODE"
                if ($s -eq "quarantined") { Write-Fail "scoop: $app QUARANTINED. Verify: scoop search $name" }
                else { Write-Fail "scoop: $app, will retry" }
            }
        }
        Save-SetupState
        Update-SessionPath
    }
}

# ---------------------------------------------------------------- 5. runtimes
if (-not $SkipRuntimes) {

    Write-Stage "Store Python aliases"
    $aliasScript = Join-Path $RepoRoot "windows\python-alias.ps1"
    if (Test-Path $aliasScript) { & $aliasScript -Disable } else { Write-Note "python-alias.ps1 missing" }

    # ----- pyenv-win -----
    # Installed and kept current, but no Python version is installed
    # automatically. Pick one yourself:  pyenv install 3.13.1
    #
    # Note: pyenv-win's own `pyenv update` is broken on Windows 11. It parses
    # python.org with the deprecated htmlfile COM object and fails with "This
    # command is not supported", leaving the version list frozen at 2022.
    # lib/pyenv-update.ps1 rebuilds the cache directly instead.
    Write-Stage "Python (pyenv-win)"
    if (Test-Cmd pyenv) {
        $updater = Join-Path $RepoRoot "lib\pyenv-update.ps1"
        if (Test-Path $updater) {
            $newest = (& $updater -MinVersion 3.12 -Quiet | Select-Object -Last 1)
            if ($newest) { Write-Ok "version cache rebuilt, newest available $newest" }
            else { Write-Note "cache rebuild returned nothing" }
        } else {
            Write-Note "lib\pyenv-update.ps1 missing, version list will be stale"
        }

        $installed = (pyenv versions 2>$null | Out-String).Trim()
        if ($installed) {
            Write-Ok "installed: $(($installed -split "`n" | ForEach-Object { $_.Trim() }) -join ', ')"
        } else {
            Write-Note "no Python installed. Install one with: pyenv install <version>"
        }
    } else {
        Write-Fail "pyenv not on PATH. Restart the shell and re-run."
    }

    # ----- uv -----
    # A peer to pyenv, not a replacement. Provides fast dependency resolution
    # and tool installs. Does not take over `python`.
    Write-Stage "uv"
    if (Test-Cmd uv) {
        uv self update 2>&1 | Out-Null
        Write-Ok "uv $(uv --version 2>$null)"

        foreach ($tool in @("ruff","pre-commit")) {
            uv tool install $tool --quiet 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "uv tool: $tool" } else { Write-Note "uv tool $tool" }
        }
    } else {
        Write-Fail "uv not on PATH"
    }

    # ----- pip -----
    # Only meaningful once a Python is active.
    Write-Stage "pip"
    if (Test-Cmd python) {
        python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
        $pipV = (python -m pip --version 2>$null)
        if ($pipV) { Write-Ok $pipV } else { Write-Note "pip not available in the active Python" }
    } else {
        Write-Skip "no active Python. Run: pyenv install <version> ; pyenv global <version>"
    }
    Write-Stage "Node (fnm)"
    if (Test-Cmd fnm) {
        fnm install --lts 2>&1 | Out-Null
        fnm default lts-latest 2>&1 | Out-Null
        Write-Ok "Node LTS, fnm default set"
        fnm env --use-on-cd --shell power-shell | Out-String | Invoke-Expression
    } else { Write-Fail "fnm not on PATH" }

    Write-Stage "Azure CLI extensions"
    if (Test-Cmd az) {
        $have = (az extension list --output tsv --query "[].name" 2>$null)
        foreach ($ext in @("azure-devops")) {
            if ($have -contains $ext) { Write-Skip "az extension $ext"; continue }
            az extension add --name $ext --only-show-errors 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "az extension $ext" } else { Write-Fail "az extension $ext" }
        }
    } else { Write-Note "az not on PATH yet. Restart the shell and re-run." }
}

# ---------------------------------------------------------------- 6. config links
if (-not $SkipLinks) {
    Write-Stage "Configuration"

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
        } else { Write-Note "no global git identity found" }
    } else { Write-Skip "git/.gitconfig.local exists" }

    $links = @(
        @{ Source = "git\.gitconfig";       Target = "$HOME\.gitconfig" }
        @{ Source = "git\.gitconfig.local"; Target = "$HOME\.gitconfig.local" }
        @{ Source = "powershell\Microsoft.PowerShell_profile.ps1"; Target = $PROFILE.CurrentUserCurrentHost }
    )

    foreach ($l in $links) {
        $src = Join-Path $RepoRoot $l.Source
        if (-not (Test-Path $src)) { Write-Skip "$($l.Source) missing"; continue }
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
    } catch { Write-Fail "module $mod : $($_.Exception.Message)" }
}

# ---------------------------------------------------------------- 8. Terminal
if (-not $SkipTerminal) {
    Write-Stage "Windows Terminal"
    $patch = Join-Path $RepoRoot "terminal\patch-settings.ps1"
    if (Test-Path $patch) { & $patch } else { Write-Note "patch-settings.ps1 missing" }
}

# ---------------------------------------------------------------- 9. WSL2
if (-not $SkipWsl) {
    Write-Stage "WSL2"
    $distros = ""
    if (Test-Cmd wsl) { $distros = (wsl --list --quiet 2>$null | Out-String) -replace "`0","" }

    if ($distros -match "Ubuntu") {
        Write-Skip "Ubuntu provisioned"
        wsl --set-default-version 2 2>&1 | Out-Null
    }
    elseif (Test-Elevated) {
        wsl --install -d Ubuntu --no-launch 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok "Ubuntu installed. Launch it once to create your user." }
        else { Write-Fail "wsl --install (exit $LASTEXITCODE). A reboot may be needed." }
    }
    else {
        Write-Host "  requesting elevation for this stage only..." -ForegroundColor DarkGray
        try {
            $p = Start-Process pwsh -Verb RunAs -Wait -PassThru -ArgumentList `
                "-NoProfile","-Command","wsl --install -d Ubuntu --no-launch; wsl --set-default-version 2"
            if ($p.ExitCode -eq 0) { Write-Ok "Ubuntu installed" } else { Write-Fail "elevated WSL install returned $($p.ExitCode)" }
        } catch { Write-Fail "WSL install declined: $($_.Exception.Message)" }
    }
}

# ---------------------------------------------------------------- 10. Explorer tweaks
# Last, because it restarts Explorer.
if (-not $SkipTweaks) {
    Write-Stage "Explorer and shell preferences"
    $tweaks = Join-Path $RepoRoot "windows\tweaks.ps1"
    if (Test-Path $tweaks) { & $tweaks } else { Write-Note "windows\tweaks.ps1 missing" }
}

# ================================================================ REPORT
$elapsed = (Get-Date) - $started

Write-Host ""
Write-Host ("=" * 72) -ForegroundColor DarkGray
Write-Host " INSTALLED" -ForegroundColor Magenta
Write-Host ("=" * 72) -ForegroundColor DarkGray

Update-SessionPath
$inv = Get-Inventory

$w1 = 14; $w2 = 26; $w3 = 10
Write-Host ("  {0,-$w1} {1,-$w2} {2,-$w3} {3}" -f "TOOL","VERSION","SOURCE","PATH") -ForegroundColor DarkGray
Write-Host ("  " + ("-" * 68)) -ForegroundColor DarkGray

foreach ($t in $inv) {
    if ($t.Version) {
        $short = if ($t.Path -and $t.Path.Length -gt 40) { "..." + $t.Path.Substring($t.Path.Length - 37) } else { $t.Path }
        Write-Host ("  {0,-$w1} " -f $t.Tool) -ForegroundColor White -NoNewline
        Write-Host ("{0,-$w2} " -f $t.Version) -ForegroundColor Green -NoNewline
        Write-Host ("{0,-$w3} " -f $t.Source) -ForegroundColor DarkGray -NoNewline
        Write-Host $short -ForegroundColor DarkGray
    } else {
        Write-Host ("  {0,-$w1} " -f $t.Tool) -ForegroundColor White -NoNewline
        Write-Host ("{0,-$w2} " -f "NOT FOUND") -ForegroundColor Red -NoNewline
        Write-Host ("{0,-$w3}" -f $t.Source) -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------- health report
if ($healthJob) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkGray
    Write-Host " MACHINE HEALTH" -ForegroundColor Magenta
    Write-Host ("=" * 72) -ForegroundColor DarkGray

    try {
        $lines = Receive-Job -Job $healthJob -Wait -ErrorAction SilentlyContinue
        Remove-Job $healthJob -Force -ErrorAction SilentlyContinue

        foreach ($line in $lines) {
            if ($line -notmatch "^(OK|WARN|FAIL|INFO)\|") { continue }
            $parts  = $line -split "\|", 3
            $status = $parts[0]; $label = $parts[1]; $value = $parts[2]

            $color = switch ($status) {
                "OK"   { "Green" }
                "WARN" { "Yellow" }
                "FAIL" { "Red" }
                default { "DarkGray" }
            }
            Write-Host ("  {0,-6} " -f "[$status]") -ForegroundColor $color -NoNewline
            Write-Host ("{0,-16} " -f $label) -ForegroundColor White -NoNewline
            Write-Host $value -ForegroundColor Gray
        }
    } catch {
        Write-Host "  health report unavailable: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- issues
$issues      = Get-Issues
$quarantined = @(Get-QuarantinedPackages)

Write-Host ""
Write-Host ("=" * 72) -ForegroundColor DarkGray
Write-Host " SUMMARY" -ForegroundColor Magenta
Write-Host ("=" * 72) -ForegroundColor DarkGray
Write-Host ("  elapsed: {0:hh\:mm\:ss}" -f $elapsed) -ForegroundColor DarkGray

if ($issues.Count -eq 0) {
    Write-Host "  no issues" -ForegroundColor Green
} else {
    Write-Host "  $($issues.Count) issue(s):" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
}

if ($quarantined.Count -gt 0) {
    Write-Host ""
    Write-Host "  Quarantined after repeated failures (skipped on future runs):" -ForegroundColor Yellow
    $quarantined | ForEach-Object {
        Write-Host ("    {0}  ({1} attempts, {2})" -f $_.Package, $_.Attempts, $_.Error) -ForegroundColor DarkGray
    }
    Write-Host "  Fix the IDs in packages/, then run: .\setup.ps1 -RetryFailed" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Next:" -ForegroundColor Cyan
Write-Host "    restart Windows Terminal to load the profile"
Write-Host "    launch Ubuntu once from Start to create your WSL user"
Write-Host "    .\update.ps1              keep everything current"
Write-Host "    .\windows\block-mdm.ps1 -Status   check enrollment posture"
Write-Host ""
