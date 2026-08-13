# PowerShell 7 profile. Symlinked to $PROFILE by setup.ps1.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ---------- PATH ordering ----------
# pyenv-win and uv both provide a `python` shim. pyenv must win, otherwise
# `python` resolves unpredictably depending on install order.
$pyenvRoot = "$HOME\.pyenv\pyenv-win"
if (Test-Path $pyenvRoot) {
    $env:PYENV      = "$pyenvRoot\"
    $env:PYENV_ROOT = "$pyenvRoot\"
    $env:PYENV_HOME = "$pyenvRoot\"
    foreach ($p in @("$pyenvRoot\bin","$pyenvRoot\shims")) {
        if ($env:Path -notlike "*$p*") { $env:Path = "$p;$env:Path" }
    }
}

$scoopShims = "$HOME\scoop\shims"
if ((Test-Path $scoopShims) -and ($env:Path -notlike "*$scoopShims*")) {
    $env:Path = "$scoopShims;$env:Path"
}

# ---------- fnm, with automatic version switching per directory ----------
if (Get-Command fnm -ErrorAction SilentlyContinue) {
    fnm env --use-on-cd --shell power-shell | Out-String | Invoke-Expression
}

# ---------- PSReadLine ----------
if (Get-Module -ListAvailable -Name PSReadLine) {
    Import-Module PSReadLine
    Set-PSReadLineOption -PredictionSource HistoryAndPlugin
    Set-PSReadLineOption -PredictionViewStyle ListView
    Set-PSReadLineOption -EditMode Windows
    Set-PSReadLineOption -HistoryNoDuplicates
    Set-PSReadLineKeyHandler -Key Tab       -Function MenuComplete
    Set-PSReadLineKeyHandler -Key UpArrow   -Function HistorySearchBackward
    Set-PSReadLineKeyHandler -Key DownArrow -Function HistorySearchForward
}

if (Get-Module -ListAvailable -Name Terminal-Icons) {
    Import-Module Terminal-Icons
}

# ---------- Aliases ----------
Set-Alias -Name ll    -Value Get-ChildItem
Set-Alias -Name which -Value Get-Command

function ..  { Set-Location .. }
function ... { Set-Location ..\.. }

function gs  { git status -sb }
function gd  { git diff @args }
function gco { git checkout @args }
function gp  { git pull --rebase }
function gl  { git log --oneline --graph --decorate -20 }

function pt  { python -m pytest @args }
function ptv { python -m pytest -vv @args }
function dt  { dotnet test @args }
function db  { dotnet build @args }

function dot     { Set-Location "C:\work\.dotfiles" }
function reload  { . $PROFILE }
function envup   { & "C:\work\.dotfiles\update.ps1" }
