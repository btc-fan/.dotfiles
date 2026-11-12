# Security model

What protects you when an agent makes a mistake or reads a hostile web page, issue or file. Short and factual. The install steps are in [INSTALL.md](INSTALL.md); the gates are in [README.md](../README.md), section 1.

## Layers, from strongest to weakest

| Layer | What it stops | Where |
|---|---|---|
| Box per project (server) | project code and services touching the host | `ubuntu-server` branch, `proj` |
| OS sandbox for host agents | reading your keys, writing outside the project, talking to unknown hosts | Claude managed settings; Codex `/etc/codex/requirements.toml` |
| No sudo for agents | root on the host | sudoers (server) and the `no-sudo` gate |
| No planted config | a workspace file that starts a process (project `.mcp.json`, project or user settings hooks) | Claude managed `strictPluginOnlyCustomization: ["hooks", "mcp"]` |
| Gates | honest mistakes: unaudited installs, secrets in commits, PRs without the required parts | router hooks |
| GitHub settings | a bad push reaching main | fine-grained per-repo token, branch protection, push protection (owner step) |

Gates are lint, not a sandbox: a script file or an unusual command can pass them. The sandbox and the box are the real boundary.

## Claude sandbox (Linux, managed settings)

- On for every session; `failIfUnavailable`, no unsandboxed retry.
- Reads denied: `~/.ssh`, `~/.config/gh`, `~/.claude/.credentials.json`, `~/.codex/auth.json`, `~/.config/ai/secrets.env`, `~/.hermes/.env`.
- Writes only: the project folder, `/tmp`, tool caches, `~/.local/state/ai`.
- Network through the sandbox proxy. Pre-allowed: GitHub, npm, PyPI, crates.io, the Go proxy, context7. Other hosts ask in an interactive session and are refused in a headless one.
- git over SSH does not work inside the sandbox: use HTTPS remotes.
- Outside the sandbox but still behind a permission prompt: `git push` (always asks) and the read-only `gh` forms (`gh pr view|list|diff|checks`, `gh issue view|list`, `gh repo view`, `gh run view|list`, which run without a prompt). Every other `gh` command asks.
- Rule for agents (root AGENTS.md): a network or permission error is final; do not try another path; tell the owner the command and the error.

## Codex

- `/etc/codex/requirements.toml` allows only `read-only` or `workspace-write` sandboxes and the `untrusted` or `on-request` approval modes. Default: `workspace-write` with `on-request`; network is off in `workspace-write`.
- Gap: Codex cannot deny reads of files in your home folder. Do not run Codex on a machine where a home-folder secret must stay hidden from it.
- Per-project MCP servers in `.codex/config.toml` load only in trusted projects.

## Planted files (box to host)

A box can write into its workspace, and a host tool may later read that workspace. Defences:
- Claude ignores servers from a project `.mcp.json` and hooks from project or user settings (managed `strictPluginOnlyCustomization`). Plugin servers and plugin hooks still load, which is why opt-in Serena is the plugin `ai-serena@ai`, turned on per project with `enabledPlugins`.
- git hooks and `core.fsmonitor` in a workspace must not run on the host (server branch: run workspace git in the box or with forced safe config).
- The escape tests E1 to E4 in [ACCEPTANCE.md](ACCEPTANCE.md) prove these on each server.

## What you do by hand

- Replace a broad `gh` token with a fine-grained per-repo token. Turn on branch protection and push protection on GitHub. (Also in the [INSTALL.md](INSTALL.md) checklist.)
- Never set `EXA_API_KEY` (it turns OMC's web-search server back on).
