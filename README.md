# Dotfiles (Windows)

Windows development environment, scripted. This is the `windows` branch; `main`
is the macOS equivalent and is not merged into this one.

## Install

    git clone https://github.com/btc-fan/.dotfiles.git C:\work\.dotfiles
    cd C:\work\.dotfiles
    git checkout windows

Read `PRECONDITIONS.md` and complete it once per machine, then:

    .\bootstrap.ps1    # verify, read-only
    .\setup.ps1        # install and link, idempotent

Both run unelevated. Only the preconditions need admin.

## Layout

    bootstrap.ps1               precondition checker, read-only, exit 1 on failure
    setup.ps1                   installer, idempotent, collects errors
    PRECONDITIONS.md            one-time manual machine setup
    docs/DECISIONS.md           every design decision and why
    lib/link.ps1                symlink helper, replaces GNU stow
    terminal/patch-settings.ps1 Windows Terminal settings patcher

## Principles

- `setup.ps1` is safe to run any number of times
- Nothing aborts the run; failures are collected and reported at the end
- Elevation is a precondition, never a runtime requirement
- Config files are symlinked from the repo, except where an app rewrites its
  own config (Windows Terminal), which is patched instead
- Package manifests are curated by hand, not exported wholesale

## Status

Foundation complete: package managers, shell, symlink capability, long paths.
Package manifests and config files are pending agreement on the tool list.
See the Open section of `docs/DECISIONS.md`.
