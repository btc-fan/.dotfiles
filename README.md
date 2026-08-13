# Windows Dotfiles

Scripted setup for a Windows development environment. Clone, run two commands, walk away. Safe to re-run any time.

This is the `windows` branch. `main` is the macOS equivalent and is not merged into this one; they share intent, not code.

---

## Quick start

```powershell
git clone https://github.com/btc-fan/.dotfiles.git C:\work\.dotfiles
cd C:\work\.dotfiles
git checkout windows

.\bootstrap.ps1     # verify the machine is ready. Read-only.
.\setup.ps1         # install and configure everything.
```

`bootstrap.ps1` will refuse to pass until the items in `PRECONDITIONS.md` are done. It prints the exact fix command for anything missing.

**Run unelevated.** The only stage that needs admin is WSL2, which requests it for a single child process. Scoop misbehaves when run as administrator.

---

## What runs, in order

`setup.ps1` executes ten stages. Every stage is idempotent: re-running skips what is already done. Nothing aborts the run. Failures are collected and printed in the summary.

| # | Stage | What it does |
|---|-------|--------------|
| 0 | Preflight | Runs `bootstrap.ps1`. Aborts if the machine is not ready. |
| 1 | Self-update | Refreshes winget sources, upgrades all installed winget packages, updates Scoop. Slow. |
| 2 | winget packages | Installs everything in `packages/winget.txt`. |
| 3 | Visual Studio | Installs VS 2026 Community with the workloads in `packages/visualstudio.txt`. 20-40 min, several GB. |
| 4 | Scoop | Adds buckets, installs everything in `packages/scoop.txt`. |
| 5 | Runtimes | Python via pyenv-win and uv, Node via fnm, Azure CLI extensions. |
| 6 | Config links | Extracts git identity to an untracked file, then symlinks configs into place. |
| 7 | PS modules | PSReadLine, Terminal-Icons. |
| 8 | Terminal | Patches Windows Terminal settings.json. |
| 9 | WSL2 | Installs Ubuntu. Requests elevation if not already elevated. |
| 10 | Explorer tweaks | Hidden files, file extensions, dark mode. Restarts Explorer, so it runs last. |

Then it prints an inventory table of every tool and its actual version, a machine health report, and a summary of issues.

---

## Flags

```powershell
.\setup.ps1 [-SkipPreflight] [-SelfUpdate] [-SkipPackages]
            [-SkipVisualStudio] [-SkipRuntimes] [-SkipWsl] [-SkipLinks]
            [-SkipTerminal] [-SkipTweaks] [-SkipHealth]
            [-RetryFailed] [-ResetState]
```

| Flag | Effect |
|------|--------|
| `-SkipPreflight` | Do not run `bootstrap.ps1` first. |
| `-SelfUpdate` | Also upgrade every already-installed package first. Off by default: slow, and `update.ps1` is the right place for it. |
| `-SkipPackages` | Skip winget and Scoop installs. Useful for re-linking configs only. |
| `-SkipVisualStudio` | Skip the 20-40 minute Visual Studio install. |
| `-SkipRuntimes` | Skip Python, Node, and Azure CLI configuration. |
| `-SkipWsl` | Skip WSL2. Avoids the UAC prompt. |
| `-SkipLinks` | Do not symlink config files. |
| `-SkipTerminal` | Do not touch Windows Terminal settings. |
| `-SkipTweaks` | Do not change Explorer settings or restart Explorer. |
| `-SkipHealth` | Do not run the machine health report. |
| `-RetryFailed` | Retry packages that were quarantined after repeated failures. |
| `-ResetState` | Discard install state and treat every package as new. |

### Recommended invocations

```powershell
# Fast validation pass. Catches bad package IDs in ~5 minutes.
.\setup.ps1 -SelfUpdate -SkipVisualStudio -SkipWsl

# Full run. Go make coffee.
.\setup.ps1 -SelfUpdate

# After fixing package IDs in packages/.
.\setup.ps1 -SelfUpdate -RetryFailed

# Re-apply configs only, no installs.
.\setup.ps1 -SkipPreflight -SelfUpdate -SkipPackages -SkipRuntimes -SkipWsl
```

---

## What gets installed

No version pins anywhere. Latest stable, always.

### winget (`packages/winget.txt`)

**Shell and terminal**

| Package | ID |
|---|---|
| PowerShell 7 | `Microsoft.PowerShell` |
| Windows Terminal | `Microsoft.WindowsTerminal` |

**Development**

| Package | ID |
|---|---|
| Git | `Git.Git` |
| .NET SDK 10 | `Microsoft.DotNet.SDK.10` |
| Azure CLI | `Microsoft.AzureCLI` |
| VS Code | `Microsoft.VisualStudioCode` |

**QA and containers**

| Package | ID |
|---|---|
| Postman | `Postman.Postman` |
| Docker Desktop | `Docker.DockerDesktop` |

**Security**

| Package | ID |
|---|---|
| Bitwarden | `Bitwarden.Bitwarden` |
| Tailscale | `tailscale.tailscale` |

**Browsers and comms**

| Package | ID |
|---|---|
| Chrome | `Google.Chrome` |
| Teams | `Microsoft.Teams` |
| Telegram | `Telegram.TelegramDesktop` |

**Utilities**

| Package | ID | Purpose |
|---|---|---|
| Snipaste | `liule.Snipaste` | Screenshots with pinning |
| Ditto | `Ditto.Ditto` | Clipboard history |
| WinRAR | `RARLab.WinRAR` | Archives |
| Logi Options+ | `Logitech.OptionsPlus` | Mouse and keyboard |
| Simplenote | `Automattic.Simplenote` | Notes |
| Grammarly | `Grammarly.Grammarly` | Writing |
| WinDirStat | `WinDirStat.WinDirStat` | Disk usage treemap |
| LockHunter | `CrystalRich.LockHunter` | Find and kill whatever is locking a file |

### Visual Studio (`packages/visualstudio.txt`)

Installed separately from the main manifest, because `winget install Microsoft.VisualStudio.Community` installs only the core shell. No .NET, no test tooling. The result cannot open a solution. This file lists workloads passed to the installer via `--override`.

Current workloads: ManagedDesktop, NetWeb, Azure, Data. Plus the .NET Core SDK, NuGet, and Git components.

To change workloads after install, use the Visual Studio Installer app. The script will not modify an existing installation.

### Scoop (`packages/scoop.txt`)

| Package | Purpose |
|---|---|
| `main/pyenv` | pyenv-win, Python version manager |
| `main/uv` | Fast Python package and version manager |
| `main/fnm` | Node version manager, switches automatically per directory |
| `main/delta` | Syntax-highlighting git diff pager. Required by `git/.gitconfig`. |

### Runtimes configured by stage 5

- **Python**: pyenv-win installs the latest stable 3.x and sets it global. uv installs its own managed Python plus `ruff` and `pre-commit` as tools. Both are present deliberately: pyenv for habit, uv for project work.
- **Node**: fnm installs the latest LTS and sets it default. The PowerShell profile enables `--use-on-cd`, so entering a directory with an `.nvmrc` or `.node-version` switches automatically.
- **Azure CLI**: adds the `azure-devops` extension.

### PATH ordering

pyenv-win and uv both provide a `python` shim. The profile forces pyenv's `bin` and `shims` directories to the front of PATH so `python` resolves predictably regardless of install order.

---

## What gets configured

| Config | Symlinked to | Notes |
|---|---|---|
| `git/.gitconfig` | `~\.gitconfig` | Contains no identity |
| `git/.gitconfig.local` | `~\.gitconfig.local` | Untracked. Generated from your existing global identity on first run. |
| `powershell/Microsoft.PowerShell_profile.ps1` | `$PROFILE` | |

Symlinks are created by `lib/link.ps1`, the GNU stow replacement. It is non-destructive: an existing real file is backed up to `<name>.bak-<timestamp>` before being replaced.

### Windows Terminal

`terminal/patch-settings.ps1` patches `settings.json` in place rather than symlinking it, because Terminal rewrites that file whenever anything changes in the GUI, which would clobber a link. It sets:

- default profile to PowerShell 7, so new tabs do not land in 5.1
- `multiLinePasteWarning: false` and `largePasteWarning: false`

A timestamped backup is taken before the first modification.

### Explorer (`windows/tweaks.ps1`)

All HKCU, no elevation needed. Only writes what differs, and only restarts Explorer if something actually changed.

- show hidden files
- show file extensions for known types
- full path in the title bar
- Explorer opens to This PC
- all folders in the navigation pane
- Task View button hidden
- dark mode for apps and system
- Start menu web search disabled

Showing protected OS files is deliberately left off. It clutters every folder with `desktop.ini`. Uncomment in the script if you want it.

---

## Optional scripts

These are **not** called by `setup.ps1`. Run them deliberately.

### `windows/block-mdm.ps1`

Prevents silent Entra registration and MDM enrollment on a personal device.

Signing into Teams or Outlook on Windows shows "Allow my organization to manage my device", pre-checked, buried in a login flow. Accepting it registers the device with Entra and, if the tenant has automatic enrollment on, enrolls it into MDM. One checkbox hands an employer management rights over hardware you paid for.

Two layers are applied:

1. `BlockAADWorkplaceJoin = 1` policy in HKLM
2. Disabling the triggers on the `Automatic-Device-Join` scheduled task, which is more reliable than disabling the task itself

Signing into individual apps still works. You get "Sign in to this app only" instead of device-wide registration.

```powershell
.\windows\block-mdm.ps1 -Status     # read-only, no elevation
.\windows\block-mdm.ps1 -Block      # elevated
.\windows\block-mdm.ps1 -Unblock    # elevated
```

**Safety guard**: refuses to run on a device that is already Entra joined, domain joined, or enterprise joined, since that indicates corporate hardware. Removing management from an employer-owned machine is a policy violation. Override with `-Force` only if you are certain you own the device.

**Tradeoff**: if your employer uses Conditional Access requiring a registered or compliant device, work resources stop working on this machine. That is the intended result.

### `windows/privacy.ps1`

Telemetry, advertising, suggestions, AI features, and location.

**Honest limit**: on Windows 11 Home and Pro you cannot disable telemetry. Microsoft treats `AllowTelemetry=0` as `1` on these editions, so Required diagnostic data keeps flowing. Only Enterprise, Education, and Server honour a true off. This script caps collection at the lowest level your edition permits and stops the optional layers. That is a real reduction, not a shutdown.

Windows Update, Defender, and security patching are unaffected.

```powershell
.\windows\privacy.ps1 -Status                    # read-only
.\windows\privacy.ps1 -Apply                     # elevated
.\windows\privacy.ps1 -Apply -Category Telemetry,AI   # selected categories
.\windows\privacy.ps1 -Revert                    # elevated
```

Categories: `Telemetry`, `Advertising`, `Suggestions`, `AI`, `Location`, `Services`.

Originals are captured to `.privacy-original.json` before any change, so `-Revert` restores what you actually had rather than a guessed default.

`-Category Location` disables location services entirely, including Find My Device. Skip it if you want weather or maps to work.

### `windows/debloat.ps1`

Clones and launches [Win11Debloat](https://github.com/Raphire/Win11Debloat) for interactive app removal. The GUI is intentional: you choose what goes. Blanket automated removal is how people lose the Microsoft Store permanently.

```powershell
.\windows\debloat.ps1            # elevated
.\windows\debloat.ps1 -Update    # pull latest first
.\windows\debloat.ps1 -CLI       # text menu instead of GUI
```

Creates a system restore point first. Prints keep and remove reference lists before launching.

**Never remove**: Microsoft Store (winget's msstore source needs it, and it is unrecoverable), App Installer (that *is* winget), WebView2 Runtime (Teams and Postman break), Microsoft Edge (WebView2 dependency), Windows Terminal, .NET runtimes.

**Safe to remove**: Copilot, Recall, Click to Do, Widgets, Cortana, Xbox apps, Solitaire, Clipchamp, 3D Viewer, Mixed Reality, Weather, News, Bing Search, Teams Personal, OneDrive consumer, Get Help, Tips, Feedback Hub, Maps, People.

**Windows feature updates undo this.** Apps come back, telemetry re-enables, preferences reset. Re-run after every major update.

---

## `update.ps1`

Refreshes everything to latest stable. Run periodically.

```powershell
.\update.ps1                 # everything
.\update.ps1 -SkipRuntimes   # packages only
```

Covers: winget sources and all packages, Scoop apps plus cleanup, pyenv-win latest Python, uv self-update and tools, fnm latest LTS, `az upgrade`, PowerShell modules.

Aliased in the profile as `envup`.

---

## Install state

`setup.ps1` records outcomes in `.setup-state.json` (gitignored).

| Status | Meaning |
|---|---|
| `installed` | Verified present. Always skipped. |
| `failed` | Attempt failed. Retried on the next run. |
| `quarantined` | Failed twice. Skipped unless `-RetryFailed`. |

Quarantine exists so a wrong package ID is not retried forever on every run. When something is quarantined, the summary tells you which package, how many attempts, and the exit code. Fix the ID in `packages/`, then run with `-RetryFailed`.

`-ResetState` wipes the file entirely.

---

## Machine health report

Runs as a background job during the install, so it costs no wall-clock time, and prints at the end. Read-only.

Reports: machine and Windows version, CPU, memory, uptime, free disk (Visual Studio alone wants 30-50 GB), Windows activation status, Entra and domain join state, MDM enrollment, Group Policy presence, Defender status, Secure Boot, TPM, BitLocker, virtualization (WSL2 and Docker need it), pending reboot, last patch date, Developer Mode, long path support.

Checks that need elevation degrade to INFO rather than failing.

Disable with `-SkipHealth`.

---

## Layout

```
bootstrap.ps1                 precondition checker, read-only, exit 1 on failure
setup.ps1                     main installer, 10 stages, idempotent
update.ps1                    refresh everything to latest stable
PRECONDITIONS.md              one-time manual machine setup
docs/DECISIONS.md             every design decision and why

packages/
  winget.txt                  GUI apps and runtimes
  scoop.txt                   CLI tools and version managers
  visualstudio.txt            VS workloads passed via --override
  Export-Packages.ps1         snapshot this machine for the next one

lib/
  common.ps1                  shared helpers, PATH refresh, output formatting
  link.ps1                    symlink helper, replaces GNU stow
  state.ps1                   install state, retry limit, quarantine
  health.ps1                  machine posture report
  inventory.ps1               probes tools directly for real versions
  mdm.ps1                     accurate join and enrollment detection

git/.gitconfig                tracked git config, no identity
powershell/                   PowerShell 7 profile
terminal/patch-settings.ps1   Windows Terminal settings patcher

windows/
  tweaks.ps1                  Explorer and shell preferences
  privacy.ps1                 telemetry, ads, AI, location
  block-mdm.ps1               prevent silent MDM enrollment
  debloat.ps1                 Win11Debloat wrapper
```

---

## Principles

- **Idempotent.** Every script is safe to run repeatedly.
- **Nothing aborts.** Failures are collected and reported, not fatal.
- **Elevation is a precondition, never a runtime requirement.** Only WSL2 requests it, for one child process.
- **Reversible.** Anything that changes system state captures the original first and offers a revert.
- **Manifests are curated by hand.** `Export-Packages.ps1` produces a snapshot for comparison, but the `.txt` files stay hand-maintained so setup does not drag along everything you ever trialled.
- **No version pins.** Latest stable, always.
- **Honest about limits.** Where something cannot actually be done on this Windows edition, the script says so rather than pretending.

---

## Recommended first-run sequence

On a fresh machine, after `PRECONDITIONS.md`:

```powershell
.\bootstrap.ps1                                        # verify
.\setup.ps1 -SelfUpdate -SkipVisualStudio -SkipWsl # validate package IDs, ~5 min
# fix any failed IDs in packages/, then:
.\windows\privacy.ps1 -Apply                           # elevated, fast
.\windows\debloat.ps1                                  # elevated, pick apps, reboot
.\setup.ps1 -SelfUpdate                            # full run, ~40 min
.\setup.ps1 -SelfUpdate -SkipPackages              # re-apply tweaks debloat may have reset
.\windows\block-mdm.ps1 -Block                         # elevated, personal devices only
```

Debloat before the full install: Win11Debloat touches some of the same Explorer keys as `tweaks.ps1`, so running setup again afterward puts them back.

---

## Differences from `main` (macOS)

| main | windows |
|---|---|
| Homebrew + Brewfile | winget + Scoop |
| `setup.sh` (bash) | `setup.ps1` (PowerShell 7) |
| GNU stow | `lib/link.ps1` symlinks, needs Developer Mode |
| zsh + `.zshrc` | PowerShell 7 + `$PROFILE` |
| pyenv + xz + LDFLAGS | pyenv-win + uv |
| gvm | not carried over |
| pinentry-mac | Gpg4win if needed |
| `defaults write com.apple.finder` | `windows/tweaks.ps1` |
| `npx playwright install-deps` | removed, Linux only |
| mas | `winget --source msstore` |

Not carried over: raycast (PowerToys Run is the equivalent), little-snitch, disk-arbitrator, omnidisksweeper (WinDirStat replaces it), zsh, stow, xz.