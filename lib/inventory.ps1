<#
.SYNOPSIS
    Reports what is actually installed and at what version.
.DESCRIPTION
    Probes each tool directly rather than trusting the package manager, so the
    output reflects reality. Returns objects; the caller formats them.
#>

function Get-ToolVersion {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Command,
        [string[]]$Args = @("--version"),
        [string]$Pattern,
        [string]$Source = ""
    )

    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $cmd) {
        return [pscustomobject]@{ Tool = $Name; Version = $null; Source = $Source; Path = $null }
    }

    $raw = $null
    try {
        $raw = (& $Command @Args 2>&1 | Out-String).Trim()
    } catch {
        $raw = $null
    }

    $version = $null
    if ($raw) {
        if ($Pattern) {
            $m = [regex]::Match($raw, $Pattern)
            if ($m.Success) { $version = $m.Groups[1].Value }
        }
        if (-not $version) {
            $m = [regex]::Match($raw, "(\d+\.\d+(\.\d+)?(\.\d+)?)")
            if ($m.Success) { $version = $m.Groups[1].Value }
        }
        if (-not $version) { $version = ($raw -split "`n")[0].Trim() }
    }

    [pscustomobject]@{
        Tool    = $Name
        Version = $version
        Source  = $Source
        Path    = $cmd.Source
    }
}

function Get-Inventory {
    $tools = @(
        @{ Name = "PowerShell";    Command = "pwsh";    Args = @("--version");  Source = "winget" }
        @{ Name = "winget";        Command = "winget";  Args = @("--version");  Source = "builtin" }
        @{ Name = "Scoop";         Command = "scoop";   Args = @("--version");  Source = "installer" }
        @{ Name = "Git";           Command = "git";     Args = @("--version");  Source = "winget" }
        @{ Name = "delta";         Command = "delta";   Args = @("--version");  Source = "scoop" }
        @{ Name = "pyenv";         Command = "pyenv";   Args = @("--version");  Source = "scoop" }
        @{ Name = "Python";        Command = "python";  Args = @("--version");  Source = "pyenv" }
        @{ Name = "uv";            Command = "uv";      Args = @("--version");  Source = "scoop" }
        @{ Name = "fnm";           Command = "fnm";     Args = @("--version");  Source = "scoop" }
        @{ Name = "Node";          Command = "node";    Args = @("--version");  Source = "fnm" }
        @{ Name = "npm";           Command = "npm";     Args = @("--version");  Source = "fnm" }
        @{ Name = ".NET SDK";      Command = "dotnet";  Args = @("--version");  Source = "winget" }
        @{ Name = "Azure CLI";     Command = "az";      Args = @("version","--query",'"azure-cli"',"-o","tsv"); Source = "winget" }
        @{ Name = "Docker";        Command = "docker";  Args = @("--version");  Source = "winget" }
        @{ Name = "VS Code";       Command = "code";    Args = @("--version");  Source = "winget" }
    )

    foreach ($t in $tools) {
        Get-ToolVersion -Name $t.Name -Command $t.Command -Args $t.Args -Source $t.Source
    }
}

function Get-WingetInventory {
    param([string[]]$ManifestIds)

    $listing = (winget list --accept-source-agreements 2>$null | Out-String)

    foreach ($id in $ManifestIds) {
        [pscustomobject]@{
            Package = $id
            Present = $listing -match [regex]::Escape($id)
        }
    }
}
