# Manual Preconditions (Windows)

One time per machine. These cannot live in `setup.ps1` because they require
elevation, require a reboot, or install the shell that runs the script.

`bootstrap.ps1` verifies every item and prints the exact fix for anything
missing. Run it before `setup.ps1`.

## 1. OS baseline

Windows 11, or Windows 10 22H2 (build 19045) minimum. Check with `winver`.

## 2. winget

Ships with Windows 11 as part of App Installer.

    winget --version

Missing? Install App Installer from the Microsoft Store, or grab the
`.msixbundle` from https://github.com/microsoft/winget-cli/releases

## 3. PowerShell 7

5.1 is the OS default and is not the target shell. It cannot be upgraded in
place, so 7 installs alongside it.

    winget install --id Microsoft.PowerShell --exact --source winget --accept-package-agreements --accept-source-agreements

Close the terminal, open a PowerShell tab (black icon), not Windows PowerShell
(blue icon). Verify with `$PSVersionTable.PSVersion`, expect 7.x.

## 4. Execution policy

    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

## 5. Scoop

User scope, no admin. Buckets are added by `setup.ps1`, not here.

    irm get.scoop.sh | iex

## 6. Developer Mode

Grants `SeCreateSymbolicLinkPrivilege` so `setup.ps1` can create symlinks
without elevation. This is the basis of the whole dotfiles model.

Settings > System > For developers > Developer Mode = On

Or in an elevated pwsh:

    New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -Name AllowDevelopmentWithoutDevLicense -Value 1 -PropertyType DWORD -Force

## 7. Long path support

Lifts the 260-character cap. Needed for `node_modules` nesting and deep .NET
build output. Both halves are required, the OS flag and git's own.

Elevated pwsh:

    New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
    git config --system core.longpaths true

## 8. Reboot

Developer Mode and long paths may not take effect until a reboot.
`bootstrap.ps1` tests symlink creation empirically and will tell you if a
reboot is still outstanding.

## Elevation summary

Only steps 6 and 7 need admin. Everything else, including all of `setup.ps1`,
runs as a normal user.

## Then

    cd C:\work\.dotfiles
    git checkout windows
    .\bootstrap.ps1
    .\setup.ps1
