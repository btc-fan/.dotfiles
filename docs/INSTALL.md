# Install

Full steps. The short version is in `README.md`, section 2. What each tool is: [TOOLS.md](TOOLS.md). What the root rules are: [AGENTS-MD.md](AGENTS-MD.md).

## Before you start

- A base setup: `~/.dotfiles` (branch `ubuntu-server` on a server). Follow its README first.
- git. On Ubuntu: an admin user with sudo (the main user has none).
- Facts about the Ubuntu server: Ubuntu 26.04 with Rust coreutils (`chown -h` and `stat -c` act differently), a CPU without AVX2 (RTK is built from source), no desktop, a second user `hermes` for Hermes.
- Do not run a real install on a machine before the dry run. Read the dry run.

## Steps

1. As the admin (never from the main user's home: root must not run code an agent can change), clone the
   branch once into a root-owned folder:
```
sudo git clone --branch ai <repo URL> /opt/ai-setup
```
   The main user may keep `~/.dotfiles-ai` as a work tree for editing; root never runs it (install.sh
   refuses to run as root from a folder owned by anyone but root or the admin).
2. Dry run. `--update` fetches `origin/ai` and fast-forwards the clone first (it refuses a dirty clone or
   rewritten history), then runs the updated script:
```
sudo /opt/ai-setup/install.sh --update --for-user <user> --dry-run
```
3. Install (and every later update: the same command):
```
sudo /opt/ai-setup/install.sh --update --for-user <user>
```
   macOS (one user, no admin layer): `~/.dotfiles-ai/install.sh`, no sudo.
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
| `--docs-server` | Gone: Grounded Docs was dropped. Install removes an existing Grounded Docs server (recorded). |
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
- RTK hook: on by default everywhere is the goal (see `install.sh --help` for the current switch). Install only changes agent configuration, never projects, databases or services.
- Plugins that the design dropped (caveman, the context7 plugin) are reported, not removed. The installer prints the remove command.

## Manual steps per machine

- Claude Code login. Codex device-code login. Hermes provider keys (`hermes setup`).
- Codex: on Linux admin installs the ai-core, RTK, Ponytail and i-have-adhd hooks live in `/etc/codex/hooks.json` (managed: no trust step for any user; the plugin copies are switched off). On macOS, or a Linux install without admin, install writes trust hashes for ai-core and RTK, and you open `/hooks` once for Ponytail and i-have-adhd. Also open it when ai-doctor lists one of ours as untrusted.
- SEO and blog skills from Hermes and Codex: Hermes never hands off to Claude; it follows the skill files in `/opt/agent-plugins/claude-seo` and `/opt/agent-plugins/claude-blog` itself (no Claude login for hermes). Codex hands off only when Claude is logged in for that user and you approved a network run for it; otherwise it follows the same skill files.
- GitHub: replace the broad gh token with a fine-grained per-repo token (only the repos agents work on, the least scopes), and enable branch protection and push protection on GitHub. Agents use the `gh` CLI (the GitHub MCP was dropped).
- claude.ai connectors (Gmail, Calendar, Drive) are off on Linux installs (`"disableClaudeAiConnectors": true` in `/etc/claude-code/managed-settings.json`), so unattended agents cannot reach your mail. To keep them: `install.sh --for-user <user> --keep-claudeai-connectors`.
- oh-my-claudecode is the pinned Claude plugin `oh-my-claudecode@omc` (as on the Mac), exa MCP off. Run `/oh-my-claudecode:omc-setup` once in Claude.
- claude-seo and claude-blog are installed but off (about 12k tokens per session each). Turn one on for one project: `ai-adopt --tools seo` (or `blog`), or put `"enabledPlugins": {"claude-seo@agricidaniel-claude-seo": true}` in that project's `.claude/settings.json`.
- Claude: `/seo setup` then `/seo doctor`, once, in a project with claude-seo on.
- `~/.config/ai/secrets.env`: GitHub token, provider keys, `DISCORD_ALLOWED_USERS` for Hermes, webhook copy for notifications.
- Serena and graphify are installed but off; turn them on per project: `ai-adopt --tools serena,graph`. Then `serena download-ls-dependencies <language>` once.
- Notifications on Linux: webhook file readable by the user. How the user reads it (a user copy or a root helper) is documented in `ai/bin/claude-notify`. Without the webhook it does nothing.
- Per project: `ai-adopt` for an existing repo, `ai-start` for a new one.
- Claude Bash sandbox (Linux): commands run in bubblewrap with no access to `~/.ssh`, `~/.config/gh`, the Claude/Codex logins and `secrets.env`; git over SSH does not work inside it (use HTTPS remotes). If Claude refuses to start with a sandbox error, run `sudo ai-doctor --for-user <user>`: it checks bubblewrap and the AppArmor profile.
- Skip a gate for a real exception (owner only): `sudo ai-gate-skip <gate> <minutes, max 60> <why>`.

## Verify

```
ai-doctor
ai-sync --check
```
`ai-sync --check` fails when a copied rule block (Codex, Hermes) differs from the source. Fix it with `ai-sync`. After each `git pull`, `ai-sync` should run (install the git hook once with `ai-sync --install-hook`).
Then spot-check three things:
- New Claude session starts with "ADHD MODE ACTIVE (always-on)".
- `claude mcp list` shows context7 (plus serena or playwright only in a project that turned them on).
- `rtk gain --history` grows after you run `git status` in a session.

## Remove or revert

Three levels. The full text is in `README.md`, section 8.

| Level | Command | Removes |
|---|---|---|
| 1 | `~/.dotfiles-ai/uninstall.sh [--dry-run]` | only what the install added, and restores what it replaced (reads `managed-keys.json`) |
| 2 (**coming**) | `~/.dotfiles-ai/uninstall.sh --purge-config` | level 1, plus the whole config and state folders of the agents. First a backup tarball, then you type `purge` |
| 3 (**coming**) | `~/.dotfiles-ai/uninstall.sh --purge-all` | level 2, plus the agents and tools the installer added |

Level 1 keeps on purpose: `~/.config/ai/secrets.env`, logins, `~/.serena`, plugin data folders and the backups in `~/.local/state/ai/backup`. No level touches your projects, boxes, databases or the server base.
Per-tool cleanup steps are in each `ai/rules/<tool>.md`, section Setup checklist.

## Not done yet (UNVERIFIED)

- The `ai` branch is not pushed. The `git fetch origin ai` step works only after the push.
- `install.sh` behavior on a real server: tested only after the build is done.
