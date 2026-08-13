# Decisions

Running record of every choice made for the Windows branch: what was decided,
why, and where it is enforced.

| # | Decision | Rationale | Enforced in |
|---|---|---|---|
| 1 | Repo at `C:\work\.dotfiles` | Not `$HOME`. Scripts resolve their own location, never hardcode a path | `$RepoRoot` in every script |
| 2 | Package managers: winget + Scoop | winget for GUI apps and MS-ecosystem runtimes, Scoop for CLI tools at user scope with no admin | `PRECONDITIONS.md`, `bootstrap.ps1` |
| 3 | Chocolatey not used | Overlaps winget, needs admin per install, messier uninstalls | n/a |
| 4 | Shell is PowerShell 7 | 5.1 is the OS default and cannot be upgraded in place. All scripts target 7 | `bootstrap.ps1` version gate |
| 5 | `stow` replaced by a symlink helper | No stow on Windows. `New-Item -ItemType SymbolicLink` covers the same model | `lib/link.ps1` |
| 6 | Developer Mode required | Grants `SeCreateSymbolicLinkPrivilege` so links work unelevated. Without it the model needs elevation or degrades to file copies | `PRECONDITIONS.md`, `bootstrap.ps1` |
| 7 | Long paths enabled | The 260-char cap breaks `node_modules` and deep .NET build trees. Needs the registry flag AND `git config --system core.longpaths` | `PRECONDITIONS.md`, `bootstrap.ps1` |
| 8 | Execution policy `RemoteSigned` (CurrentUser) | Minimum to run local unsigned scripts. Not `Unrestricted` | `PRECONDITIONS.md`, `bootstrap.ps1` |
| 9 | Scoop buckets: main, extras, nerd-fonts, versions | extras for GUI/dev tools, nerd-fonts for prompt glyphs, versions for pinning | `setup.ps1` |
| 10 | Terminal settings patched, not symlinked | Terminal rewrites `settings.json` on any GUI change, breaking a symlink. Patch only the keys we care about | `terminal/patch-settings.ps1` |
| 11 | Terminal defaults: pwsh 7 profile, paste warnings off | New tabs must not land in 5.1. The multi-line paste warning blocks scripted workflows | `terminal/patch-settings.ps1` |
| 12 | Symlink capability tested empirically | The Developer Mode flag can be set but not effective until reboot. Trust behaviour, not the registry value | `bootstrap.ps1` |
| 13 | Elevation steps are preconditions, not setup steps | Only 3 exist: Developer Mode, long paths, `core.longpaths`. `setup.ps1` runs fully unelevated | `PRECONDITIONS.md` |
| 14 | git identity kept out of the tracked config | The tracked `.gitconfig` will be symlinked over `~\.gitconfig`. Identity lives in an untracked `.gitconfig.local` pulled in via `[include]` | pending |
| 15 | The mac `Brewfile` is not ported blindly | Every package is reviewed before entering a manifest | pending |

## Verified on this machine

- PowerShell 7.6.4
- winget v1.9.25200
- Scoop v0.5.3, buckets: main, extras, versions, nerd-fonts
- Developer Mode: on, unelevated symlink creation confirmed working
- LongPathsEnabled: 1, `core.longpaths`: true
- git identity: Mihail Lungu / lungumihai25@gmail.com

## Open

- Tool and application list (runtimes, QA tooling, editors, CLI, work apps)
- Python strategy: `uv` vs `pyenv-win`
- .NET SDK version(s)
- WSL2 distro and provisioning
- Whether to track Terminal theme and font settings
