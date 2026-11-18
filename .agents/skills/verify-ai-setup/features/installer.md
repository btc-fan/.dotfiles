# Installer dry run

`install.sh --dry-run --yes --profile <p> --user` prints every step it would do for that profile and changes nothing on the real machine.

## Sub-features

- `install-plan`: the 13 steps with `[dry-run]` lines and `planned:` lines.
- `install-sources`: the newest stable version per tool (`ai/lib/resolve.py`).
- `install-profile`: dev-mac and server give their own plan.

## How to get to it (user POV)

- The owner runs `~/.dotfiles-ai/install.sh --dry-run` before an install or update.
- The setup-rollout skill runs it as the first check on a machine.

## Driving it with verify

Preconditions: a launched run (any kind) with `doctor: PASS`.

- **Plan dev-mac.** Run `$H drive install dev-mac`. Expect `rc: 0`, `real files changed: none`, and `Profile: dev-mac (--profile).` in `NN-install-dev-mac.txt`.
- **Plan server.** Run `$H drive install server`. Expect `rc: 0`, `real files changed: none`, `Profile: server (--profile).`.
- **Side effects.** Read `files in the temp HOME after`. Seen on 2026-11-18: `.claude/.claude.json`, `.claude/backups/...`, `.local/state/gh/device-id` (the `claude` and `gh` CLIs write these when the dry run asks them for versions).

## Gotchas

- The dry run is not offline: step 2 asks npm, PyPI, GitHub and git remotes for the newest versions.
- The dry run calls `claude` and `gh`; they write the 3 files above into the temp HOME. With the real HOME they would write into `~/.claude` and `~/.local/state/gh`. Always use the driver, never a bare dry run, for proof.
- `--user` never calls sudo. The system mode (`--for-user`) and the root-owned clone are not driven here.

## Proof paths

- success: both profiles end `rc: 0` with a plan.
- cancel: n/a (`--yes` answers every question; the dry run has no prompt to back out of).
- error: `$H drive install laptop` exits with the usage text (the driver allows only dev-mac and server). An unknown profile in `install.sh` itself is in `ai/tests/test_profiles.py`.
- empty: n/a (a fresh temp HOME is the empty state of every drive).
- persistence: n/a (a dry run stores nothing; `real files changed: none` is the proof).
- Unreachable: a real install. Blocked by the rules of this repo's agents (never run `install.sh` for real from a worktree). Route tried: none.
