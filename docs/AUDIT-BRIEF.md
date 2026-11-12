# Audit brief: the home server and the AI dev factory

This file is the starting point for an independent auditor (a fresh agent session or a person).
It explains what the two branches build, why, what was changed in each fix round, what is proven
on the real server, what is only tested offline, and what is still open. Read it first, then the
files it points to. It is written for the state of 2026-11-12.

Words used here:
- **main user**: the server's normal login. Claude Code, Codex and opencode run as this user.
- **agent user**: a second login for the Hermes Discord agent.
- **admin**: the only login with passwordless sudo. The owner uses it for installs.
- **box**: one Incus system container per project.
- **workspace**: the folder on the host that holds a box's code (`/srv/proj/work/<box>`), mounted
  as `/srv/app` inside the box.

## 1. What the owner wants (the goals everything is measured against)

One owner (a developer), plus 1 or 2 friends later. He wants AI coding agents to build and run
his projects on a home Ubuntu server, safely, also from his phone.

| # | Goal |
|---|---|
| G1 | "Impeccable out of the box": the server and the AI layer are built ONLY from two public dotfiles branches (`ubuntu-server`, `ai`). Every server change goes through a branch, is pulled and run on the server. No hand edits. Re-runnable. Full removal possible. |
| G2 | Disks: a 500 GB HDD is the main data disk (Postgres, Docker, a 24/7 crawler), a second 500 GB HDD holds the backups, a 320 GB HDD is the ZFS pool for boxes, the SSD is the system. Data stays safe and recoverable after a power cut. |
| G3 | Security first: SSH keys only, growing IP bans, a separate admin, agents WITHOUT sudo (only an allow-listed wrapper), no secrets in the public repo, audit every package before install, pin every version, telemetry off. Agents must not be able to harm the server even if they run malicious code. |
| G4 | One isolated box per project (tiers try, mvp, long), easy to wipe and rebuild, agents cannot overlap. One `proj` tool. Snapshots and backups. Every agent knows that "make me an app" means "make a box". |
| G5 | One root config for all agents (Claude Code with oh-my-claudecode, Codex, Hermes on Discord, opencode, more later): the same house rules and gates, installed by the admin for a user. |
| G6 | Top priority: dev-factory quality. Agents follow the guardrails (gates, PR flow), use the right skills, look up library docs instead of coding from memory, navigate and extend code quickly, and do not start from zero every session. |
| G7 | Token efficiency (RTK always on, small always-on context). |
| G8 | Phone control: Hermes on Discord, alert and info channels, approvals from Discord, later a "root broker" (a Discord button that makes a root service run one listed command). |
| G9 | Real test loops up to production, edge cases, every plugin proven useful or removed. |
| G10 | Keep it simple. Later the same approach on the owner's two Macs. |

Rules for the repo itself: it is PUBLIC. No secrets (one exception: a free context7 API key the
owner approved, in `ai/marketplace/plugins/ai-core/mcp/context7.sh`), no IP addresses, host names,
disk serials, e-mails or employer names, no machine- or project-specific rules (real values live
only in `host.env` on the server). Never the long dash (U+2014). Simple English.

## 2. The two branches

| Branch | Local checkout used for development | What it builds |
|---|---|---|
| `ubuntu-server` | `dotfiles-ubuntu-server` | The host: security, disks, backups, alerts, Incus boxes, `proj` and `proj-agent`. |
| `ai` | `dotfiles-ai` (a worktree) | The agent layer: rules, plugins, hooks, gates, MCP servers, per-agent adapters. |

How they are run on the server (both as admin, both from root-owned clones, never from the main
user's home):
```
# server layer (root-owned copy, see setup.sh)
sudo /opt/server-setup/setup.sh [--only <step>]
# AI layer (root-owned clone, fast-forwards to origin/ai and refuses a dirty tree)
sudo /opt/ai-setup/install.sh --update --for-user <main user>
```
Both scripts refuse to run as root from a folder owned by another user. This was a finding of the
second audit (an agent could have edited the scripts in its own home before the admin ran them).

## 3. Server layer (`ubuntu-server`)

Read: `README.md`, `docs/HOSTING.md`, `docs/AGENTS-hosting.md`, `docs/NOTES.md`, `setup.sh`,
`lib/common.sh`, `steps/*.sh`, `files/proj/proj`, `files/sbin/*`, `host.env.example`, `tests/`.

### Steps
| Step | Does |
|---|---|
| 00-preflight | OS checks, quirks (Ubuntu 26.04 with Rust coreutils and sudo-rs, no AVX2 CPU). |
| 10-security | Hostname, admin user, SSH hardening with a rollback timer, `--drop-main-sudo`, `MAIN_SUDO`, ufw, fail2ban with growing bans and recidive, unattended upgrades, sysctl, Tailscale. Removes stale passwordless sudo files for the main user. |
| 20-always-on | Power and sleep settings, unattended boot after power loss. |
| 30-disks | Mounts by UUID with nofail, the ZFS pool for boxes, the backup disk. |
| 40-tools | Docker (localhost only, live-restore), Postgres, CLI tools, pinned apt keys. |
| 50-alerts | Discord alerts: failed units, SMART health (never self-tests: owner rule), disk use, boot cause, SSH logins, load. |
| 55-shared-users | The agent user, shared group, `AGENT_SUDO=none`. |
| 60-backups | Postgres dumps, mirror to the backup disk, work snapshots. |
| 70-hosting | Incus, profiles, bridge and egress ACL, `proj`, `proj-agent`, sudoers allow-list, workspaces (nosuid mount, git guard). |
| 90-verify | Over 120 checks; must end with 0 FAIL. |

### Boxes and the workspace
- `proj` (`files/proj/proj`) is the only tool that creates, wipes, snapshots, restores, forks,
  rebuilds, backs up and expires boxes. Tiers: try (expires), mvp, long (never wiped, nightly export).
- Profiles: `box-base` (isolated ID map, `security.nesting` because Ubuntu 26.04 needs it for
  networking, limits), bridge with an egress ACL that blocks the home LAN, the tailnet and link-local.
- Markers `/etc/proj-host` and `/etc/proj-box` tell an agent where it is; house rules are pushed
  into boxes (`/etc/proj-rules/AGENTS.md`).
- Shared workspace (owner choice): code lives on the host in `/srv/proj/work/<box>`, mounted into
  the box with `shift=true` (idmapped). Host agents edit with their normal tools; code runs only in
  the box: the box tool `exec` (MCP server `box` in ai-core, which runs the root-owned `/usr/local/sbin/proj-agent`). Claude's sandbox blocks unix sockets, so there is no socket client; plain `proj-agent <sub>` only outside a sandbox.
- `proj-agent` (`files/sbin/proj-agent`) is the only sudo an agent has: new try/mvp box, list,
  status, snapshot, doctor, logs, restart a service in a box, exec, ports, url. It refuses long
  tier, wipe and delete.

### Security mechanisms added after the audits (all proven on the server)
1. **Workspace nosuid,nodev.** With `shift=true`, root in a box writes files owned by real uid 0
   on the host. A setuid-root program made in a box ran as root on the host (proven). Now
   `/srv/proj/work` is a bind mount onto itself with `nosuid,nodev` (systemd mount unit, ordered
   before Incus). Proof: the same program now runs with the main user's uid. `proj selftest`
   repeats this probe; `proj doctor` checks the mount.
2. **Main user without sudo.** `host.env MAIN_SUDO=none`: out of the sudo group, the sudoers rule
   is empty; only `proj-agent` and a root-owned Discord webhook helper remain allow-listed. Reason:
   agents run as the main user and could fake a sudo prompt to catch the password.
3. **git guard** (`files/sbin/git-workspace-guard`, installed as `/usr/local/bin/git`). A box can
   write `.git/config` and `.git/hooks` in its workspace, and host agents run git there. For any git
   call that touches a workspace: hooks off, fsmonitor off, explicit bare repos only, no ext::
   transport, no submodules, and every repo config file may hold only allow-listed keys. The first
   version used a block-list; the second audit found 3 bypasses, so it was being rewritten as an
   allow-list at the time of writing (check its current state and its tests in `tests/`).
4. **Root runs only root-owned clones** (`setup.sh` and the AI `install.sh`).
5. **stdin**: `incus` create, copy, launch and restore commands read YAML from stdin when it is
   not a terminal. Piped input once made the client eat memory until the kernel killed it, and
   `proj selftest` hung over ssh. Every such call in `proj` now gets `</dev/null`.

### Restore and snapshots
- `proj snapshot` also archives the workspace (`/srv/proj/work/.snapshots/<box>/<label>.tar.zst`,
  root only, newest 10, dependency and cache folders left out).
- `proj restore` was broken on ZFS (a rollback past newer snapshots is refused, and restore made a
  newer safety snapshot first). It now works like `git reset`: lists and removes the later
  snapshots, archives the current workspace as `pre-restore-<date>`, backs up long boxes first,
  and always starts the box again.

### In progress at the time of writing (server-fix round, check what landed)
Big-database backup straight to the backup disk (7 daily, 4 weekly), longer dump
history, monthly restore drill; ZFS events and inodes in alerts; weekly read-only SMART attribute
digest; reboot-required notice; a daily digest message in Discord (the owner chose this instead of
an outside heartbeat); the 2-minute `systemd-networkd-wait-online` boot wait; the workspace mount
as a hard dependency of Incus; restore extracting as the main user; egress ACL review; ZFS atime.

## 4. AI layer (`ai`)

Read: `README.md`, `ai/SPEC.md`, `docs/INSTALL.md`, `docs/SECURITY.md`, `docs/TOOLS.md`,
`docs/CONTEXT.md`, `docs/AGENTS-MD.md`, `docs/EXTENDING.md`, `docs/ACCEPTANCE.md`, `install.sh`,
`ai/lib/{common.sh,aiconf.py,root-guard.sh}`, `ai/adapters/*.sh`, `ai/routing.yaml`,
`ai/agents-md/*.md`, `ai/rules/*.md`, `ai/marketplace/plugins/*`, `ai/bin/*`, `ai/tests/*`.

### Shape
- **One root rule set**: `ai/agents-md/*.md` is rendered by `ai/bin/ai-render` into one
  `AGENTS.md` (about 10.6 KB now, cap 30 KB) and delivered to each tool's native place: Claude
  (`/etc/claude-code/CLAUDE.md` managed, plus user level), Codex (`~/.codex/AGENTS.md`), Hermes
  (its SOUL.md block and plugin), opencode. Per-tool usage contracts in `ai/rules/*.md`, copied to
  `~/.config/ai/rules` per user.
- **Native extension points** instead of a sync tool: a local plugin marketplace `ai` with plugins
  `ai-core` (router hooks, gates, context7 MCP, skills), `ai-serena` and `ai-playwright` (opt-in per
  project). A sync tool (rulesync) was piloted and rejected because it replaced files.
- **Router** (`ai/marketplace/plugins/ai-core/hooks/router.py` + `hooklib.py`) reads the rendered
  `ai/routing.yaml` (v4, 21 rows). It runs on prompt, before and after tool calls, and at session
  start. It injects short lines and logs proofs to `~/.local/state/ai/fired.jsonl` and
  `misses.jsonl`. Rows that only nudged and were ignored in the logs were removed in round 4.
- **Gates** (block, logged to `gates.log`): `audit-before-install` (no install without an
  `agent-audit` pass in the last 24 h), `secret-scan` (staged files and commit messages, also `-F`,
  stdin and heredocs), `pr-rules`, `no-sudo` (every sudo/su/doas/pkexec blocked except
  `sudo proj-agent` too; box work = the box tool (MCP server `box`: list, new, exec, logs, status, restart, ports, url, snapshot, doctor, help); outside a sandbox also plain `proj-agent <subcommand>`; never sudo). The only way past a gate is the owner's
  `sudo ai-gate-skip <gate> <minutes max 60> <why>` (root-owned file); a variable in the command
  text does nothing.
- **Supply chain**: every tool is pinned in `ai/pins.env` and audited by `ai/bin/agent-audit`
  (osv-scanner, guarddog, skill-scanner). Findings stop the install unless the exact version is in
  `ai/audit-accepted.txt` with a dated reason (8 entries, each reviewed line by line by the owner's
  agent; all were false positives such as test fixtures or SSRF guards).

### Claude Code (managed settings on Linux)
- Permissions: allow list for read-only tools only (context7, narrow rtk and graphify forms with
  denies for exec/output options, read-only gh forms, WebFetch, WebSearch); Edit denies for every
  agent config and rule file.
- Sandbox: required (`failIfUnavailable`, no unsandboxed retry). Commands cannot read `~/.ssh`,
  the gh, Claude and Codex logins or the secrets files; writes only to the project, /tmp and caches;
  network through the proxy with an allow list. bubblewrap and socat installed.
- `strictPluginOnlyCustomization: [hooks, mcp]`: hooks from settings files and MCP servers from
  `.mcp.json` or `~/.claude.json` do not run, so a box cannot plant them in a workspace. Plugin
  hooks and plugin MCP servers still run; `ai-core` is force-enabled so the router and gates cannot
  be switched off; RTK runs as a managed hook.
- `disableClaudeAiConnectors: true` (the owner's mail and calendar connectors must not reach
  unattended agents).
- Plugins: ai-core (on), oh-my-claudecode 5.8.4 (pinned plugin, exa web search off), Ponytail,
  i-have-adhd (owner keeps them always on), claude-seo and claude-blog (installed, off, opt-in per
  project), ai-serena and ai-playwright (off, opt-in), 5 mattpocock skills.

### Codex
- Hooks (ai-core, RTK, Ponytail, i-have-adhd) are in `/etc/codex/hooks.json` on Linux admin
  installs: Codex loads that file as a managed layer with no trust step, proven on Codex 0.167 (an
  `npm install` was blocked by our gate inside `codex exec`). Every program in it is an absolute,
  root-owned path. macOS uses trust hashes computed from Codex's own recipe.
- `/etc/codex/requirements.toml`: sandbox read-only or workspace-write, approvals untrusted or
  on-request; default workspace-write without network. Gap: Codex cannot deny reads in the home.

### Hermes (Discord) and opencode
- Hermes: owner-only Discord bot, approvals mode "smart" (the audit recommends manual; the owner
  kept smart for now), context7 MCP, no sudo, follows skill files itself (no hand-off to Claude),
  `updates.check` off. Hermes and opencode are the least tested agents.

### Project knowledge ("do not start from zero")
- Evidence that drove the round-4 design: an eval by Vercel (a docs index inside AGENTS.md was used
  100% of the time, skills 53 to 79%), an ETH Zurich study (long context files lower success and
  raise cost; keep only non-standard facts), and our own measurement on a real repo (plain Grep and
  Read beat the Serena and graphify stack on cost and correctness, see section 6).
- So: `ai-adopt` writes two managed blocks into each repo's own `AGENTS.md`: `## Map` (at most 60
  lines: entry points, where things live, run, test, conventions) and `## Libraries` (library,
  version, context7 ID; written by `ai-libs --sync` from the lockfiles, public package names only,
  private registries detected and skipped). The session-start status line says whether the Map
  exists and whether Libraries match the lockfiles.
- Serena, graphify and Playwright are opt-in per project (`ai-adopt --tools serena,graph,browser`).
- context7 is the one docs tool. Grounded Docs and the GitHub MCP were removed (agents use `gh`).

### Install, update, removal, health
- `install.sh` (admin, `--for-user`), `--update`, `--dry-run`; every change is recorded so
  `uninstall.sh` can undo it (`default`, `--purge-config`, `--purge-all` with a backup tarball).
- `ai-sync` (git post-merge hook) refreshes a user's own files; the Hermes copies and `/etc` rules
  are refreshed only by the admin install.
- `ai-doctor` (and `sudo ai-doctor --for-user <user>`): checks for every mechanism above.
- Tests: `bash ai/tests/run.sh` (router cases, command, knowledge and setup tests; all passing at
  the time of writing; one setup test was seen to fail once and then pass, being looked at).

## 5. History: what was done, found and fixed

| When | Round | Main changes | Commits |
|---|---|---|---|
| 2026-11-10/11 | Build | Server steps, boxes, `proj`; AI installer, ai-core, router, gates, rules, docs | many, up to `04420e4` (server), `242f100` (ai) |
| 2026-11-11 | Owner security decision | Agents lose sudo; `proj-agent` allow-list; Hermes smart approvals | `f6acbfe`, `24e88c5`, `8a47499` |
| 2026-11-12 | Test loop 1 on the server | Found: Codex ran none of our hooks, Claude headless blocked by missing permissions, Grounded Docs crash loop, claude.ai connectors (owner mail) loading, hand-offs broken, docs routing missed library names, OMC not wired, rules folder missing per user | report only |
| 2026-11-12 | Fix round 2 + review | Codex hooks to /etc, permissions, connectors off, OMC plugin, seo/blog opt-in, Hermes MCP, memory design. An independent review found 2 HIGH (an allowed `rtk find` could run any command; /etc hooks resolved programs from a user-writable PATH) and several MEDIUM; all fixed | `1c4a747` |
| 2026-11-12 | Server snapshots | Workspace in snapshots, restore fixed on ZFS, stdin fixes | `0c9fd28`, `f2eabfa`, `e3508cb` |
| 2026-11-12 | Audit 1 (Fable) | Setuid escape through the workspace (proven, fixed), stale sudo rule, planted git config, host agent unsandboxed, stack too big | `7a39bfd`, `db12c45`, `df3f62e`, `2408b13`, `98b5d11` |
| 2026-11-12 | Round 4 (ai) | Sandbox, planted-config lock, Codex requirements, simplification, AGENTS.md halved, admin-clone installs | `31414f1`, `9ce77ea` |
| 2026-11-12 | Audit 2 (Fable) | Scorecard 5/10; root ran scripts from the agent's home; the big crawler database had no backup; git guard bypasses; tokens measured | server-fix round in progress (`047714f` and later) |

## 6. Measurements (from audit 2, on the real server, before round 4 was deployed)

- Always-on input tokens of a fresh Claude session: 48,926 with everything, 14,056 for Claude Code
  alone. MCP tool lists 13.7k, skill listings 9.4k. Codex: about 25k, 0.9k of it from our config.
- Round 4 removed GitHub MCP (about 10k), Grounded Docs and global Serena (about 3k), the routing
  table at start (about 2k) and halved the rules. Estimate after: about 28k total, about 14k ours,
  most of it oh-my-claudecode (about 7k) and i-have-adhd, which the owner keeps. Not yet measured.
- Navigation on a real Python repo (one run per cell): plain Grep and Read cost 30k to 157k tokens
  and were correct; the Serena and graphify stack cost 200k to 366k, once got line numbers off by
  one and once over-edited (39 lines instead of 11). TypeScript and the official LSP plugins were
  not measured.
- RTK saved about 1.4k tokens over 36 commands.

## 7. Owner decisions (keep these unless the owner changes them)

- Disks as in G2; never run SMART self-tests.
- Agents run on the host (not inside boxes) with a shared workspace; harden them. Moving the agent
  into the box may be revisited.
- No sudo for any agent, nor for the main user; admin does admin work.
- Hermes approvals "smart" for now; no hand-off from Hermes to Claude.
- Keep oh-my-claudecode, Ponytail and i-have-adhd always on; claude-seo, claude-blog, Serena,
  graphify and Playwright opt-in per project; context7 the only docs tool; `gh` instead of the
  GitHub MCP.
- Stay on Incus 6.0.5 from the Ubuntu archive for now (nosuid blocks the known setuid path).
- Daily digest in Discord instead of an outside heartbeat.
- The 8 audit acceptances in `ai/audit-accepted.txt`.

## 8. Known open items and accepted risks

- Not yet proven on the server after round 4: the Claude sandbox in real use (git, npm, uv through
  the proxy), the planted-config lock, the new token count, the opt-in plugins, Hermes changes.
- No real project has gone from idea to running in a box through all agents (G9); the results table
  in `docs/ACCEPTANCE.md` is not filled.
- Prompt injection into a host agent: the sandbox covers Bash only, not Read or MCP servers.
- Boxes have open internet (secrets in a box `.env` can leave).
- Hermes with model-decided approvals is a remote shell with judgment in the loop.
- Single old HDD for the ZFS pool; no off-site backup; no UPS.
- The Discord root broker is not built; it needs a design first (fixed menu, exact command on the
  button, single use, short expiry).
- The two Macs are not started.

## 9. How to audit

1. Read this file, then the docs named in sections 3 and 4.
2. Offline: `bash ai/tests/run.sh` in the `ai` checkout; read `tests/` in `ubuntu-server`.
3. On the server, read-only as the main user (no sudo there): `ai-doctor`, `proj-agent list`,
   `findmnt -T /srv/proj/work`, `ls -l /etc/codex /etc/claude-code`, `cat /etc/claude-code/managed-settings.json`,
   `~/.local/state/ai/{fired.jsonl,misses.jsonl,gates.log}`, `systemctl --failed`, `zpool status`.
   As admin only with the owner's OK: `sudo proj doctor`, `sudo proj selftest`,
   `sudo /opt/server-setup/setup.sh --only verify`.
4. Measure tokens with a fresh `claude -p ... --output-format stream-json --verbose` in an empty
   folder and read the first call's input tokens.
5. Score the setup against G1 to G10, list ranked risks with a concrete failure scenario and fix,
   and say what to cut.
