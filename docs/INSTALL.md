# Install

Full steps. The short version is in `README.md`, section 3.

## Before you start

- A base setup: `~/.dotfiles` (branch `ubuntu-server` on a server). Follow its README first.
- git. On Ubuntu: passwordless sudo for the main user.
- Facts about the Ubuntu server: Ubuntu 26.04 with Rust coreutils (`chown -h` and `stat -c` act differently), a CPU without AVX2 (RTK is built from source), no desktop, a second user `hermes` for Hermes.
- Do not run a real install on a machine before the dry run. Read the dry run.

## Steps

1. Add the worktree (separate folder):
```
git -C ~/.dotfiles fetch origin ai
git -C ~/.dotfiles worktree add ~/.dotfiles-ai ai
```
2. Dry run:
```
~/.dotfiles-ai/install.sh --dry-run
```
3. Install:
```
~/.dotfiles-ai/install.sh
```
4. Fill the keys. `cp ~/.dotfiles-ai/secrets.env.example ~/.config/ai/secrets.env && chmod 600 ~/.config/ai/secrets.env`, then edit.
5. Manual steps (below).
6. `ai-doctor`.

## What `install.sh` does

Each step prints `[n/N] what`. A step that is already done is skipped. Run it twice: the second run changes nothing.

1. Prerequisites: git, stow, jq, uv, node LTS, python3.
2. Pins: reads `ai/pins.env`. Every version and commit sha lives in that one file.
3. Worktree links: `~/.dotfiles/bin/claude-notify` and every `ai/bin/*` command linked into `~/.local/bin/`. The link names go into `~/.dotfiles/.git/info/exclude`.
4. `ai-render`: turns `ai/routing.yaml` into `ai/build/routing.json` and the L0 table. It joins `ai/agents-md/*.md` and the L0 table into the root file. It fails above 30 KB.
5. Agents: only those found or asked for with `--agents`. Registers the marketplace `ai` and the plugin `ai-core` with Claude and Codex. Hermes, opencode and herdr get their own registrations.
6. MCP servers: Serena, context7, GitHub, Grounded Docs through the plugin `.mcp.json`. Codex: `codex mcp add`. Playwright is not installed here: it is per project.
7. Skills: our own skill, the five pinned mattpocock skills.
8. Hooks: inside the plugin. Our own merge code only writes managed blocks (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, Hermes `SOUL.md`) and single keys for telemetry and update switches. Everything it adds is recorded in `~/.local/state/ai/managed-keys.json`.
9. Env: telemetry off and auto-update off for every tool.
10. Verify: `ai-doctor --quick`.
It ends with a summary: done, skipped, manual steps left.

Options:

| Option | Meaning |
|---|---|
| `--dry-run` | Print what would change. Change nothing. |
| `--agents a,b` | Only these agents: claude, codex, hermes, opencode, herdr. |
| `--skip-packages` | Do not install system packages. |
| `--no-rtk-hook` | Leave the RTK hook off on this machine. RTK is on by default everywhere. |
| `--yes` | Answer yes to the confirm questions. Not to the server question. |

## Ubuntu

- Packages: apt, with signed repositories.
- `/etc/claude-code/managed-settings.json` is merged: telemetry off, error reports off, auto-updater off.
- RTK is built from source (about 8 minutes). See `ai/rules/rtk.md`.
- Hermes parts run as user `hermes` (`sudo -u hermes -H`), only if that user exists.
- Linux keeps the SessionStart caffeinate entry. `/usr/local/bin/caffeinate` is a systemd-inhibit wrapper. The installer adds it if missing.
- Grounded Docs runs as a server role: the firewall allows port 6280 from the LAN and tailscale0 only.
- The server also imports `~/.dotfiles/docs/AGENTS-hosting.md` (from the `ubuntu-server` branch) into the root rules when that file exists.
- Install OMX not before 2026-11-17. The installer holds it until then.

## macOS (later)

- brew only for missing CLIs. Never `brew upgrade`.
- Never writes macOS managed settings (an employer may manage them). Environment keys go into `~/.claude/settings.json` `env`.
- RTK hook on by default (`--no-rtk-hook` to skip). Install only changes agent configuration, never projects, databases or services.
- Plugins that the design dropped (caveman, the context7 plugin) are reported, not removed. The installer prints the remove command.

## Manual steps per machine

- Claude Code login. Codex device-code login. Hermes provider keys (`hermes setup`).
- Codex: `/hooks`, trust the plugin hooks once.
- Claude: `/seo setup` then `/seo doctor`.
- `~/.config/ai/secrets.env`: GitHub token, provider keys, `DISCORD_ALLOWED_USERS` for Hermes, webhook copy for notifications.
- Serena: `serena init`, then `serena download-ls-dependencies <language>`.
- Notifications on Linux: webhook file readable by the user. How the user reads it (a user copy or a root helper) is documented in `ai/bin/claude-notify`. Without the webhook it does nothing.
- Per project: `ai-adopt` for an existing repo, `ai-start` for a new one.

## Verify

```
ai-doctor
```
Then spot-check three things:
- New Claude session starts with "ADHD MODE ACTIVE (always-on)".
- `claude mcp list` shows serena, context7, github, grounded-docs connected.
- `rtk gain --history` grows after you run `git status` in a session.

## Uninstall

```
~/.dotfiles-ai/uninstall.sh
```
Removes only what `managed-keys.json` lists. Per-tool cleanup steps are in each `ai/rules/<tool>.md`, section Setup checklist.

## Not done yet (UNVERIFIED)

- The `ai` branch is not pushed. The `git fetch origin ai` step works only after the push.
- `install.sh` behavior on a real server: tested only after the build is done.
