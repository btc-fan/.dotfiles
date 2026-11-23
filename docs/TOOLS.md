# Tools and agents

Every tool in the setup: what it is, why we chose it, how it works here, and what to do when two tools overlap.
Each entry ends with the link to its usage contract in `ai/rules/`. The contract is the exact rule set. This page is the explanation.

Words used below:
- **Global**: installed on every machine, active in every project.
- **Opt-in**: only in a project that asked for it (`ai-start` or `ai-adopt` writes the project layer).
- **Pin**: the version or commit that was audited at intake. Since 2026-11-14 the installed version is the newest stable release (SPEC 23): `ai/pins.env` says where each tool comes from, `~/.local/state/ai/resolved.json` says what is installed.
- **Contract**: `ai/rules/<tool>.md`. Sections: vendor rules, when and when not, enforcement, proof, setup.

## Contents

1. [Agents and harnesses](#1-agents-and-harnesses)
2. [MCP servers](#2-mcp-servers)
3. [Plugins, skills and CLI tools](#3-plugins-skills-and-cli-tools)
4. [Audit and safety tools](#4-audit-and-safety-tools)
5. [Overlaps and how we decide](#5-overlaps-and-how-we-decide)
6. [How they interact](#6-how-they-interact)
7. [Defaults and configuration](#7-defaults-and-configuration)
8. [Overlaps: one job each](#8-overlaps-one-job-each)

## 1. Agents and harnesses

An agent is the program that talks to a model and runs tools. A harness is an agent plus extras that orchestrate it.

### Claude Code (and oh-my-claudecode)

- **What.** Anthropic's coding agent in the terminal. oh-my-claudecode (OMC) adds a workflow on top: plan, execute, review, verify, plus team runs and loops. It is installed as a pinned Claude plugin (`oh-my-claudecode@omc`, tag v5.8.4, commit checked), on servers too (owner decision 2026-11-12). The old npm route (`oh-my-claude-sisyphus`) stays available with `AI_OMC_WIRING=cli`.
- **Why.** It is the main agent. It has the richest hook system, which the router and the gates need.
- **How it works here.** The plugin `ai-core` is installed from our local marketplace `ai`. Claude reads the root rules through an `@import` line in a managed block of `~/.claude/CLAUDE.md`. Example: you type "/oh-my-claudecode:autopilot build a CSV to JSON tool". OMC runs its autopilot skill. The OMC magic keywords are off (`OMC_SKIP_HOOKS=keyword-detector` in the env, ticket 15): the word "autopilot" in a normal prompt starts nothing. Our rules still win on a clash: the 60-word reply limit and the confirm-first rules beat OMC defaults.
- **`omc launch` and CLAUDE-omc.md.** When `~/.claude/CLAUDE-omc.md` exists with the OMC markers, `omc` / `omc launch` (OMC CLI 5.8.x, `prepareOmcLaunchConfigDir` in `dist/cli/launch.js`) starts Claude with the config dir `~/.claude/.omc-launch/`, whose CLAUDE.md is a copy of CLAUDE-omc.md only (settings, plugins, skills and hooks are mirrored). So `~/.claude/CLAUDE.md` and our rules import are not loaded there. When CLAUDE-omc.md exists, `install.sh` and `ai-sync` (after each pull) add the same `AI:core` import block to it, after `<!-- OMC:END -->`, never inside OMC's markers (recorded; uninstall removes it). `ai-doctor` fails when the file exists without the block. macOS only: on Linux the rules come from `/etc/claude-code/CLAUDE.md`, which every session loads (owner decision 2026-11-14).
- **OMC scope.** macOS: on everywhere. Servers: installed but off by default (owner decision 2026-11-12); on for one project with `ai-adopt --tools omc`. Where it is off, its skills, agents, hooks and MCP server do not load.
- **Scope.** Global, main.
- **Pin.** Intake: OMC 5.8.4. Installed: the newest stable tag of the plugin (`OMC_PLUGIN_SOURCE`) or npm release (`OMC_SOURCE`). Claude Code comes from the signed apt repository on Ubuntu.
- **claude.ai connectors off on servers.** The account connectors (Gmail, Calendar, Drive and the like) do not load in Claude Code on Linux installs (`disableClaudeAiConnectors` and `ENABLE_CLAUDEAI_MCP_SERVERS=false`), so an unattended agent cannot reach your mail. macOS keeps Claude's default. To keep them on a server: `install.sh --keep-claudeai-connectors` (see [INSTALL.md](INSTALL.md)).
- **Telemetry and updates off.** Managed settings (`/etc/claude-code/managed-settings.json` on Ubuntu): telemetry, error reports and auto-updater off. OMC: `{"security":{"disableAutoUpdate":true}}` and the exa web-search MCP off (`mcpServers.exa.enabled: false`) in its config, and `OMC_UPDATE_REGISTRY_BASE` pointed at a dead local address (its daily npm ping ignores the setting). `OMC_SKIP_HOOKS=keyword-detector` turns the magic keywords off. The OMC context-guard Stop hook stays on (OMC 5.8.5 has no switch for it), but `OMC_CONTEXT_GUARD_THRESHOLD=94` makes it block only near a full context. `OMC_REPLY_ENABLED` is never set.
- **Contract.** `ai/rules/omc.md`.

### Codex (with oh-my-codex)

- **What.** OpenAI's coding agent. oh-my-codex (OMX) is the OMC-like layer for Codex.
- **Why.** A second main agent: a second model family, and a way to cross-check Claude.
- **How it works here.** Codex cannot `@import`. It gets a managed block `AI:core` copied into `~/.codex/AGENTS.md`. `ai-sync` refreshes the copy after each `git pull`. The same `ai-core` plugin installs into Codex from the same folder, so the router and gates run there too. Codex asks once to trust the plugin hooks (`/hooks`). Example: `omx exec "<prompt>"` runs a non-interactive Codex task.
- **Scope.** Global, main. No cooldown since 2026-11-14: install.sh takes the newest stable OMX after its audit.
- **Pin.** Intake: Codex 0.167.0, OMX 0.22.6. Installed: the newest stable npm release of each (a Codex from another installer is left as it is).
- **Telemetry and updates off.** Codex analytics, feedback and update checks off in `config.toml`. `OMX_AUTO_UPDATE=0`, `OMX_NATIVE_AUTO_FETCH=0`. No native binaries.
- **Hook node path (owner decision 2026-11-14).** OMX writes its Codex hooks with the node it ran under. With Homebrew node that is a versioned Cellar path (`/opt/homebrew/Cellar/node/<version>/bin/node`), which is gone after the next `brew upgrade node`. After each install `install.sh` points those oh-my-codex commands to Homebrew's stable link `<brew prefix>/opt/node/bin/node` when it exists (recorded; a trust hash you gave the old command moves along). Nothing else of OMX changes.
- **Warning.** The OMX template says "do not stop to ask, proceed". The root rules say the owner's confirm-first rules win. Never run OMX in a Claude session.
- **Contract.** `ai/rules/omx.md`.

### opencode

- **What.** An open-source terminal agent that talks to many model providers.
- **Where.** macOS: always installed. Linux servers: not installed by default (owner decision 2026-11-12); `AI_EXTRA_AGENTS=opencode` for install.sh brings it back.
- **Why.** It is the front-end for other models (Grok, Kimi, DeepSeek) and a fallback. Always installed.
- **How it works here.** It reads the root rules through the `instructions` key of `~/.config/opencode/opencode.json`. It reads the shared skills folder `~/.agents/skills`. It has no hooks, so no gates and no miss log inside it: only the root rules apply. Example: `opencode run "<prompt>" --format json`.
- **Scope.** Global, always installed.
- **Pin.** 1.19.5 (closed binary, audited). Never run `opencode upgrade`.
- **Telemetry and updates off.** `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_MODELS_FETCH=1`, `OPENCODE_DISABLE_LSP_DOWNLOAD=1`, and `{"autoupdate":false,"share":"disabled"}` in its config.
- **Contract.** `ai/rules/opencode.md`.

### Hermes

- **What.** A chat-gateway agent (Discord) with a daily summary.
- **Why.** You can talk to the server from your phone.
- **How it works here.** It runs as its own user `hermes`. Every change to it is made as that user and recorded in its own state file. Root rules go into a managed block of its `SOUL.md`, refreshed only by the admin command `sudo /opt/ai-setup/install.sh --update --for-user <user>`. A small plugin does the L2 and L3 routing. It uses plain skills only. No sudo. SEO and blog work: it follows the claude-seo and claude-blog skill files itself (no hand-off to Claude). Only the owner's Discord id may talk to it.
- **Scope.** Global, configured (Linux server).
- **Pin.** No installer pin exists. The version after install is recorded in `pins.env`.
- **Telemetry off.** Yes, in its config. Approvals stay manual.
- **Contract.** `ai/rules/hermes.md`.

### herdr

- **What.** A terminal multiplexer for agents: several agents in panes, with status and session ids.
- **Where.** Installed on every machine (owner 2026-11-16: its CLI gives the PR author-sessions block a real session id). `ai-doctor` checks the CLI.
- **Why.** It gives us the session ids that the PR "author-sessions" block needs, and a status view.
- **How it works here.** `herdr integration install claude|codex` adds status hooks. The agent reads its own session id with `herdr agent get "$HERDR_PANE_ID"`. The `pr-rules` gate blocks a PR body without the author-sessions block. `pr-resume` reads that block later to resume the sessions. herdr is not a harness: it makes no model call.
- **Scope.** Global, configured.
- **Pin.** The newest stable release (0.9.5 at intake). The installer takes the release binary and checks it against the sha256 in herdr's own manifest. The router also gives the author-sessions line (`main: <session id> dir: <cwd>`) without herdr, so a PR body gets a real id.
- **Telemetry and updates off.** `[update] version_check = false` and `manifest_check = false`. Never run `herdr update`.
- **Contract.** `ai/rules/herdr.md`.

### oh-my-openagent (omo), optional

- **What.** An opencode-based orchestration layer.
- **Why.** Kept as an option only. Its license limits use (internal, personal, non-commercial), and its installer is a pipe-to-bash.
- **How it works here.** Not installed. If you ask for it, a full audit comes first, then a managed block in that project's AGENTS.md. Never mix omo, OMC and OMX in one session.
- **Scope.** Optional.
- **Contract.** `ai/rules/omo.md`.

Later: Gemini CLI and Kimi CLI (wired when enabled). Grok, Kimi and DeepSeek are models, used inside opencode, OMC or OMX.

## 2. MCP servers

MCP servers give agents extra tools, and each one costs context in every session, so the global list is short: context7 from `ai/marketplace/plugins/ai-core/.mcp.json` (tool names `mcp__plugin_ai-core_<server>__*`), our `box` server from the plugin `ai-box@ai` (profile server only; tools `mcp__plugin_ai-box_box__*`), and Serena from the plugin `ai-serena@ai` (on at user scope, deferred tools; a project opts out with `no-serena`). Per project: Playwright through the plugin `ai-playwright@ai` (off at user scope, on with `enabledPlugins` in the project settings, `ai-adopt --tools browser`). Managed settings block servers from a project `.mcp.json` (a planted file in a workspace must not start a process).

### context7

- **What.** A cloud service with current docs for libraries, exposed as two MCP tools. The one docs tool (owner decision 2026-11-12: Grounded Docs dropped).
- **Why.** Training data is old. Docs in a tool call beat answers from memory.
- **How it works here.** The repo AGENTS.md has a "## Libraries" section with a context7 ID per library (written by `ai-libs --sync`). A cached ID means `query-docs` directly, no `resolve-library-id`. Otherwise `resolve-library-id`, then `query-docs`, one concept per call, at most 3 calls. Queries leave the machine, so no secrets and no private code in a query. Free plan: 1,000 calls per month; cached IDs save about half. `ai-libs` sends only public package names, once per library, and nothing at all for an ecosystem with a private index. The free key is committed in the plugin config (owner decision, one allowlisted exception to the secret scan).
- **Scope.** Global.
- **Pin.** `@upstash/context7-mcp@4.6.0`.
- **Contract.** `ai/rules/context7.md`.

### Serena (on in every project)

- **What.** A code-intelligence server. It reads and edits code by symbol through language servers.
- **Why.** A symbol lookup costs far fewer tokens than reading files, and edits by symbol are exact. On by default (owner decision 2026-11-12 evening); a project opts out with `no-serena` in `.ai/enabled`.
- **How it works here.** Global for Claude (plugin `ai-serena@ai`, on at user scope, `--context=claude-code`), Codex (`--context=codex`) and Hermes (`--context=ide`), all with `--project-from-cwd` and mode `no-memories`: no memories and no onboarding, the AGENTS.md Map is the one knowledge place. `ai-adopt` indexes each project. One Serena per agent: a user-scope `serena` in `~/.claude.json` is moved out once `ai-serena@ai` is on (saved, restored by uninstall); Codex replaces a foreign `serena` entry the same way. Tools: `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `replace_symbol_body`. Answers are cut at 40k characters; no dashboard. Section 7 has every setting.
- **Pin.** `serena-agent==2.1.0`. **Telemetry off.** `SERENA_USAGE_REPORTING=false` in the server entry's `env`.
- **Contract.** `ai/rules/serena.md`.

### box (our server for project boxes)

- **What.** An MCP server in the plugin ai-box (profile server only; a dev-mac never installs it) with one tool per box action (`mcp__plugin_ai-box_box__<name>`): list, new, exec, logs, status, restart, ports, url, snapshot, doctor, help. `exec` takes `command` (a bash string, run with `bash -lc` in the box, so pipes and `&&` work) or `argv` (a list), optional `cwd` and `timeout` up to 3600 s. `new` takes `name` and `tier` (`try` or `mvp`), optional `docker` and `pg`. It runs the root-owned `proj-agent` for the agent.
- **Why.** Agents have no sudo, and Claude's sandbox blocks unix sockets, so a shell client cannot reach `proj-agent`. An MCP tool works in Claude, Codex and Hermes alike.
- **How it works here.** Registered on server installs for Claude (plugin), Codex (`codex mcp add box`, long tool timeout) and Hermes; on a Mac it lists no tools. "Make me a small web page" ends in the tool's `new`, then `exec` to run things inside the box. `sudo proj-agent` is denied by the no-sudo gate; plain `proj-agent <sub>` works only outside a sandbox.
- **Contract.** `ai/rules/box.md`.

### GitHub: the `gh` CLI

- **What.** GitHub work (issues, pull requests, reviews) goes through `gh`. The GitHub MCP is dropped (owner decision 2026-11-12: a large tool list and a full-access token).
- **How it works here.** Read-only by default. Writes (a PR, a comment, a merge) are outward actions: confirm first; a PR goes through the `pr-rules` gate. owner/repo comes from the origin remote.

### Playwright MCP

- **What.** A browser the agent can drive: open a page, click, take a screenshot.
- **Why.** End-to-end checks and screenshots. The vendor itself says CLI skills are cheaper than an always-on MCP, so we do not keep it always on.
- **How it works here.** Opt-in per project. `ai-adopt --tools browser` turns on the plugin `ai-playwright@ai` for that project (and writes the Codex project config), headless and isolated. Outside such a project, `ai-info` lists it as off here; the agent suggests `ai-adopt --tools browser`. The agent must not install a browser tool itself.
- **Scope.** Opt-in per project.
- **Pin.** `@playwright/mcp` 0.0.85.
- **Contract.** `ai/rules/playwright.md`.

## 3. Plugins, skills and CLI tools

### graphify (on in every project)

- **What.** Builds a code graph of a repo: which file calls which. Local, no LLM for code. CLI only (no MCP server).
- **Why.** "Where is X, what depends on Y" from a local graph. On by default (owner decision 2026-11-12 evening); a project opts out with `no-graph` in `.ai/enabled`.
- **How it works here.** `ai-adopt` runs `GRAPHIFY_BACKEND=none graphify extract . --code-only` (no key, nothing sent out; bare `graphify .` asks for an LLM key and fails, so never use it), gitignores `graphify-out/`, and runs `graphify hook install` (git hooks rebuild the graph after commit, checkout, merge and rebase). Agent git calls run no hooks on a server (git guard), so the router refreshes the graph itself: after a successful commit, merge, pull, checkout, switch or rebase it starts `graphify update` in the background. Query with `graphify query "..."`.
- **Pin.** 0.9.105 (PyPI `graphifyy`). **Telemetry.** None documented.
- **Contract.** `ai/rules/graphify.md`.

### RTK (Rust Token Killer)

- **What.** A command proxy that shortens the output of shell commands (git, test runs, logs) before the agent reads it.
- **Why.** Output is the biggest token cost in a coding session. Savings are up to 90%.
- **How it works here.** A hook rewrites `git status` to `rtk git status`. On Claude the hook is our wrapper `rtk-hook` (ai-core): it does nothing in auto mode, because a rewrite after the auto-mode review gave "no verdict" denials; otherwise it runs `rtk hook claude`. The router's own command rewrite also does not rewrite in auto mode (it denies with the command to run). Codex keeps `rtk hook codex`. The agent does not call it by hand. `git push` and `gh` are never rewritten (`exclude_commands`), so their output and our gates see the plain command. Exception: `uv run` is not rewritten, so in a Python project the agent types `uv run rtk pytest`. For security tools and debugging use `rtk bypass <cmd>` so findings are not cut. Check with `rtk gain --history`.
- **Scope.** Global, on by default.
- **Pin.** Intake v1.2.0. Installed: the newest stable release, built from source (`cargo --locked`). On macOS with the Homebrew formula `rtk` (same project): `brew upgrade rtk` after the audit of the release tag, only when the homebrew/core formula is exactly that version (else a WARN and the installed rtk stays), no Rust and no build; an older copy this setup built in `~/.local/bin` is moved to the backup folder, so one rtk stays on PATH (owner decision 2026-11-14).
- **Telemetry.** Never run `rtk telemetry enable`.
- **Contract.** `ai/rules/rtk.md`.

### Ponytail

- **What.** A plugin that pushes the agent toward the smallest correct diff.
- **Why.** Less code means less to review and less to break. It never cuts validation, error handling, security or accessibility.
- **How it works here.** Mode `full` from `~/.config/ponytail/config.json`. Vendor hooks run at session start and per prompt. Codex: on Linux admin installs the hooks run from `/etc/codex/hooks.json`; on macOS trust them once in `/hooks`.
- **Scope.** Global.
- **Pin.** Commit `96608e0` (version 5.3.3), from a read-only audited clone.
- **Telemetry and updates.** None documented. Never run `/ponytail band import` (it starts a hidden process).
- **Contract.** `ai/rules/ponytail.md`.

### i-have-adhd

- **What.** An always-on reply style: lead with the answer, short, one next action.
- **Why.** The owner reads many agent replies. It keeps them scannable.
- **How it works here.** A flag file turns it on. Its session-start hook injects "ADHD MODE ACTIVE (always-on)". It is typed-only (the model cannot invoke it), so the flag does the work. You turn it off for one session with "stop adhd mode". It does not apply to documents, PR bodies and code comments: those follow the writing style (Simplified Technical English).
- **Scope.** Global.
- **Pin.** Commit `1ecea19` (package 0.4.1).
- **Contract.** `ai/rules/i-have-adhd.md`.

### claude-seo

- **What.** Many SEO skills: site audit, page check, schema, Core Web Vitals, sitemap, hreflang, backlinks, GEO.
- **Why.** SEO work needs a method and data sources. This plugin has both.
- **How it works here.** Input is a URL or a site: `/seo audit <url>` or `/seo page <url>`. Costly or outward actions ask first (indexing submit, image generation, DataForSEO, Google sign-in). Hermes follows the skill files itself (no hand-off). Codex and opencode hand off to Claude Code with `claude -p` only when Claude is usable for that user (Codex also needs an owner-approved network run), else they follow the skill files in `/opt/agent-plugins/claude-seo`. Run `/seo setup` once per machine.
- **Scope.** Opt-in per project (owner decision 2026-11-12). Installed on every machine but off at user scope: plugin skills cannot be hidden one by one, and the two packs cost about 12k tokens per session. Turn claude-seo on for one project: `ai-adopt --tools seo` (or put `"enabledPlugins": {"claude-seo@agricidaniel-claude-seo": true}` in that project's `.claude/settings.json`). In other projects, an SEO prompt in Claude gets one line: "claude-seo is off in this project. Suggest: ai-adopt --tools seo". The opt-in is for Claude only: Codex, opencode and Hermes read the skill files on demand (no listing cost), so for them it counts as on everywhere.
- **Pin.** v2.5.0 (`219ff48`). Extension installers stay off.
- **Contract.** `ai/rules/claude-seo.md`.

### claude-blog

- **What.** 32 skills for blog posts: write, rewrite, score, fact-check, translate, plan.
- **Why.** Posts need a pipeline with checks, not one prompt.
- **How it works here.** Input is one post file, or a post to write. The router sends "write a post" to `claude-blog:blog`. Vendor gates (preflight, reviewer) prove a real run. Paid image or audio and any upload to a third party ask first. Tell it "reply short, report to a file", because it does not follow the short-reply style. Other agents: same hand-off rules as claude-seo.
- **Scope.** Opt-in per project, like claude-seo: `ai-adopt --tools blog`. Elsewhere a blog prompt gets the one-line "turn it on" suggestion.
- **Pin.** v2.3.2 (`4f9c2cb`). Never install or uninstall from v2.2.0.
- **Contract.** `ai/rules/claude-blog.md`.

### mattpocock skills (five pinned copies)

- **What.** Small workflow skills: `grilling`, `grill-me`, `wait-what`, `retro`, `writing-for-agents`.
- **Why.** Grilling stress-tests a plan before code. `writing-for-agents` keeps AGENTS.md and SKILL.md files good.
- **How it works here.** Copies at a pinned commit, in `~/.agents/skills` (shared) and linked for Claude. Example: "grill me on this plan" starts numbered question rounds with a recommended answer each. `grill-me`, `wait-what` and `retro` are typed-only: the agent can suggest them but cannot fire them. The other skills of the pack are opt-in or not used.
- **Scope.** Five global. Rest opt-in.
- **Pin.** `4ae2317`. No plugin, no `npx skills@latest`.
- **Contract.** `ai/rules/mattpocock-skills.md`.

### prompting-claude-and-codex (our own skill)

- **What.** A short guide for writing a brief to another agent.
- **How it works here.** The `prompting-others` rule fires when the agent runs `codex exec`, `claude -p`, `opencode run`, `omc ask` or `herdr agent prompt`. Example brief: goal, what is ruled out, absolute file paths, narrow scope, expected output, read-only.
- **Scope.** Global. Dated snapshot of the official docs.
- **Contract.** `ai/rules/prompting-claude-and-codex.md`.

### ui-ux-pro-max (opt-in)

- **What.** Seven design skills: UI rules, palettes, fonts, design system, banners, slides.
- **Why.** Only for projects that build a visual interface.
- **How it works here.** Enabled per project, never in the user settings. Where it is installed, `install.sh` sets it off at user scope (`AI_OFF_CLAUDE_PLUGINS` in `ai/pins.env`, owner decision 2026-11-14); `ai-adopt --tools ui` turns it on for one project. Logo, icon and image generation call a paid API: ask first. Never copy its `stack/` folder.
- **Scope.** Opt-in per project.
- **Pin.** v2.15.0 (`a38d04c`).
- **Contract.** `ai/rules/ui-ux-pro-max.md`.

### llm-wiki-compiler (opt-in)

- **What.** Compiles a folder of sources into a cited wiki the agent can query.
- **Why.** For a project that has a corpus and needs cited evidence.
- **How it works here.** Registered in that project's `.mcp.json` only. Compile and ingest cost model tokens, so the agent asks first. Not the same as the OMC wiki (see section 5).
- **Scope.** Opt-in per project.
- **Pin.** v1.5.0.
- **Contract.** `ai/rules/llm-wiki-compiler.md`.

### last30days

- **What.** One skill: what people say about a topic in the last 30 days, from Reddit, X, YouTube, Hacker News, Polymarket, GitHub and the web, ranked by engagement.
- **Why.** Current opinion and trends that docs and web search miss (owner decision 2026-11-14).
- **How it works here.** `/last30days <topic>`. Reddit, Hacker News and Polymarket work without keys. Its setup wizard (in chat, it asks first) can read browser cookies for X, install free CLIs (yt-dlp and others) and add paid keys. The topic text goes to those services. No hook since v3.39.0: the only per-session cost is the skill description (older releases had a SessionStart status hook; the update removes it). Optional one-time setup: `/last30days`, then finish or skip the wizard (skip writes `SETUP_COMPLETE=true`, `BROWSER_CONSENT=false` to `~/.config/last30days/.env`).
- **Scope.** Global for Claude, on by default (Claude plugin `last30days@last30days-skill`, newest stable tag, audited). Not installed for Codex, opencode or Hermes.
- **Pin.** Intake: v3.39.0 (`f918b49`).
- **Contract.** `ai/rules/last30days.md`.

### Toolbox (not installed)

Good tools that are not part of daily work live in `ai/TOOLBOX.md`. They are not loaded into sessions. The root rules have one pointer line. Each needs a full audit before its first install.

## 4. Audit and safety tools

### agent-audit

- **What.** Our wrapper: `agent-audit npm|pypi|dir|skill <target>`. It runs guarddog (malware rules), osv-scanner (known vulnerabilities) and a skill scanner.
- **Why.** Every tool, package, MCP server, skill and plugin is checked before it runs.
- **How it works here.** Each run appends `<time> <ecosystem> <name> <version> PASS|FAIL` to `~/.local/state/ai/audit.log`. The install gate reads that file. A missing scanner counts as a finding (fail closed). A FAIL means stop and show the owner. A FAIL, ERROR or REJECT also writes one line to `~/.local/state/ai/walls.jsonl` (ai-doctor shows 7 days).
- **Example.** `agent-audit pypi graphifyy` before `uv tool install graphifyy==0.9.105`.

### gitleaks

- **What.** A secret scanner.
- **Why.** The `secret-scan` gate runs it next to our own patterns, when it is installed.
- **Pin.** 8.30.1 (`GITLEAKS_HOLD` in `ai/pins.env`). Profile dev-mac installs it (owner 2026-11-18): the release
  archive. Its sha256 must match the pin in `ai/pins.env` (`GITLEAKS_SHA256_<OS>_<ARCH>`) and the release's checksums
  file. A new `GITLEAKS_HOLD` needs new sha256 lines. It is a release binary, so agent-audit does not scan it.

### ai-doctor

- **What.** The health check for the whole setup.
- **How it works here.** It validates the plugin, tests the router with sample inputs, checks every enabled tool has a contract, compares the copied rule blocks to the source, and reads the miss log. `ai-doctor --quick` runs at the end of the install. `--project <repo>` also checks the repo AGENTS.md budget (12 KB soft, root rules + repo file under the Codex 32 KiB read cap), Done (6 lines) and Lessons (15 lines), the tier and check targets, and in long tier the ledger and the ratchet baseline.

### Project checks (Tier 1, per adopted repo)

- **What.** One check loop per project, sized by a tier in `.ai/enabled` (`tier: try|mvp|long`, default `mvp`; `ai-adopt --tier`). `try` (prototype): check targets, Done block, `no-destroy`. `mvp` (real users soon): also the Stop hook and the PR fields `Verify:` and `Risk:`. `long` (production, money, data): also the regression ledger, the full PR fields and the ratchet.
- **ai-check-detect.** Finds the stack from lockfiles and manifests (uv, poetry, pip + pytest and ruff; npm, pnpm, yarn, bun; go; cargo) and plans `check-fast` (lint + unit, under 60 s) and `check` (everything) as one marked Makefile or justfile block. It never changes an existing target and refuses monorepos. `ai-adopt` writes the block, times `check-fast` once and puts both commands in the Map (`- Check:`). Contract: `ai/rules/check-command.md`.
- **stop-check.** A Stop hook (Claude and Codex) beside the router. It runs `check-fast` only when files changed since the session start, blocks with the last 40 lines, at most twice per tree and 4 times per chain of continuation stops (the agent's fix is checked in the continuation), and is silent on success. It stays silent while an oh-my-claudecode persistent mode of the session owns the stop. Opt out per repo: `no-stop-check`. Contract: `ai/rules/stop-check.md`.
- **Regression ledger.** `docs/REGRESSIONS.md` (one row per bug that reached main, with its test in `tests/regressions/`). The router names the R-IDs before an edit in their area; `ai-ledger --check` keeps the file honest. Contract: `ai/rules/regression-ledger.md`.
- **ai-ratchet.** Test, skip and lint counts against `.ai/ratchet.json`; they may only improve. Contract: `ai/rules/ratchet.md`.
- **Done and Lessons.** A managed 6-line Done block and a Lessons section (15 lines) in the repo AGENTS.md. Contract: `ai/rules/agents-md-done.md`.
- **Example.** `ai-adopt --tier long` in a uv + pytest repo writes the Makefile block, the Done block, `docs/REGRESSIONS.md` and `.ai/ratchet.json`, then commits them after one y/N.

### Verification skills (pstack, per project verify-<app>)

- **What.** `create-verification-skill` and `maintain-verification-skill` (pstack, MIT, Lauren Tan; github.com/cursor/plugins). The first writes a project skill `.agents/skills/verify-<app>/` that launches the real app, checks it (doctor), drives features the way a user does, keeps evidence and cleans up; plus a feature map (one file per feature). The second keeps the map honest.
- **How it works here.** Our copy in `ai/skills/` is made from the vendor copy by `ai/lib/pstack_adapt.py` (path `.cursor/skills` becomes `.agents/skills`; Codex reads project skills there, `ai-adopt` adds the committed link `.claude/skills/verify-<app>` for Claude). The adapter also makes both skills model-invocable (the agent builds the tool at the first feature task), makes step 1 cover every surface, and appends the section `Our additions` (`ai/lib/pstack_additions/`): a driver per surface, the proof set per feature, evidence in `.verify/evidence/<run>/` with the `run.log` fields the hooks read. The installer follows the newest upstream commit (audited, same transform). The session status shows the verify skill, its feature count, and "stale" after 25 code commits or 30 days since the map changed. Done order in tier mvp and long: check-fast, verify-<app> on the changed feature with evidence, only then e2e tests; the PR Verify field cites both. Contract: `ai/rules/verification-skill.md`.

### mattpocock opt-in skills (per project)

- **What.** grill-with-docs, domain-modeling, to-spec, to-tickets, tdd, codebase-design, code-review, pr, diagnosing-bugs, improve-codebase-architecture: copied and audited with the five global picks, linked only into projects that list them (`skills:` in `.ai/enabled`; default mvp and long: grill-with-docs, domain-modeling, to-spec, to-tickets, tdd).
- **How it works here.** `ai-adopt` links them into `<repo>/.claude/skills/` and `<repo>/.agents/skills/` (local links, gitignored); tickets stay in `docs/tickets/` (`docs/agents/issue-tracker.md`). Contract: `ai/rules/mattpocock-skills.md`.

## 5. Overlaps and how we decide

Some tools can do the same job. The table in `ai/routing.yaml` (`tiebreaks`) names a winner for each case. The router names the winner first and the loser never. This section explains each in words.

| Case | Winner | Loser | In words |
|---|---|---|---|
| One post file, or a post to write | `claude-blog:blog-*` | `claude-seo:seo-*` | A post file on disk is content work. |
| A URL, a domain, a whole site | `claude-seo:seo-*` | `claude-blog:blog-*` | A live site is SEO work. |
| Content brief for a page at a URL | `seo-content-brief` | `blog-brief` | The page exists, so brief by SEO. |
| Content brief for a post not yet written | `blog-brief` / `blog-outline` | `seo-content-brief` | No page yet, so brief by blog. |
| Topic cluster to write posts | `blog-cluster` | `seo-cluster` | Goal decides. |
| Topic cluster as site architecture | `seo-cluster` | `blog-cluster` | Goal decides. |
| Search Console, PageSpeed, CrUX | `seo-google` | `blog-google` | One Google login, shared. |
| Feature prompt (add, implement, build ... a feature, endpoint, page) | `grill-with-docs` then `to-spec` and `to-tickets` where the project links them, else `grilling` | writing code at once | The `feature-kickoff` skill (its description holds the EN, RO and RU words); a trivial change skips the grill. |
| Proving a change works | the project's `verify-<app>` skill, then e2e tests | "CI is green" alone | Evidence from the running app first, then a test that encodes it. |
| Tickets for a feature | `to-tickets` into `docs/tickets/` | GitHub issues | Never without the owner. |
| New app or project (kickoff) | `grilling` (typed: `/grill-me`) | OMC `deep-interview` | Kickoff uses grilling; deep-interview only when grilling is not installed. |
| "Grill me", stress-test a plan | matt `grilling` | OMC `deep-interview` | Numbered rounds, no score. |
| "Deep interview", "ambiguity score" | OMC `deep-interview` | matt `grilling` | The score is OMC's feature. |
| "Research X" | OMC `research` | matt `research` (opt-in) | One research path. |
| Code review of a diff | built-in `code-review` or OMC `review` | matt `code-review` (opt-in) | Name collision avoided. |
| Bug, stack trace | OMC `debug` / `trace` | matt `diagnosing-bugs` | One debug path. |
| Edit AGENTS.md, CLAUDE.md, SKILL.md | matt `writing-for-agents` | OMC `skillify` | settings.json goes to `update-config`. |
| Chart or dashboard styling | `dataviz` | `blog-chart`, ui-ux-pro-max | Charts have one skill. |
| A `.pptx` file | `anthropic-skills:pptx` | ui-ux-pro-max slides (HTML decks) | File type decides. |
| "Wiki" | llmwiki where the project enabled it, else OMC wiki | the other | The project marker decides. |
| Code lookup | the Map in AGENTS.md, then `graphify query`, then Serena symbols, then a narrow rg | OMC `lsp_*`, ast-grep (fallback) | One order everywhere; `no-serena` / `no-graph` skip a step. |
| Library API docs | context7 with the ID from the Libraries section | web search | Cached ID first, web last. |
| What people say about a topic now | `last30days` | OMC `research`, web search | Recent opinion and engagement: last30days. Facts and docs: the others. |

### Finding code: Map, graph, Serena, then rg

- Order in every repo: the Map section of AGENTS.md (no tool call), then `graphify query` (structure), then Serena symbol tools (definitions, references, edits), then a narrow `rg` and reading only the located lines.
- A project can opt out of Serena or graphify with `no-serena` / `no-graph` in `.ai/enabled`; then that step is skipped.
- OMC `lsp_*` and ast-grep: fallback, for diagnostics or a language Serena does not cover.
Example: "who calls `calc_price`?" starts with the Map (which module), then `graphify query "calc_price callers"`, then Serena `find_referencing_symbols` for the exact list, then a read of three lines.

### Library docs: context7, then the source

- Step 0: the Libraries section of AGENTS.md (version and context7 ID; no call at all).
- Step 1: context7 `query-docs` with that ID (`resolve-library-id` only when there is none).
- Step 2: the library source or the official site, and say that docs were not found.
Use the locked version. Never send secrets or private code in a docs query. Web search is not a docs tool: Codex too uses context7 first.

### Where project knowledge lives

The goal: an agent never explores a repo from zero. Evidence behind the design (owner decision 2026-11-12, after an independent audit): passive context in AGENTS.md is used every time, while on-demand tools and per-tool nudges are often skipped (Vercel's agent eval: an 8 KB docs index in AGENTS.md passed 100%, skills alone were never invoked in 56% of cases). Context files must stay short and hold only non-standard facts.

| Fact | Home | Made by | Refreshed when |
|---|---|---|---|
| House rules | root AGENTS.md (`~/.config/ai/AGENTS.md`, short) | ai-render | rules change |
| Where things live, how to run and test, conventions | "## Map" in the repo AGENTS.md (managed block, <= 60 lines, committed) | ai-adopt (facts from the repo, plus one read-only claude pass for conventions) | a commit adds, deletes or renames modules (`ai-docs-check` in `make check` fails on a path that is gone); `ai-adopt --refresh-map` |
| Library versions and context7 IDs | "## Libraries" in the repo AGENTS.md (managed block, committed) | `ai-libs --sync` | lockfile changes or a new ID was used |
| Code structure | `graphify-out/` (gitignored) | `ai-adopt` (unless `no-graph`) | git hooks after commit, checkout, merge, rebase; after agent git calls the router starts `graphify update` in the background |
| Session notes | OMC notepad | the agent | never project truth |

Tool folders stay out of git: `ai-adopt` writes one managed `.gitignore` block on every run (between `# >>> AI tools` and `# <<< AI tools`; your own lines are kept) for `.omc/*`, `.codex/`, `.claude/*`, `.serena/*`, `graphify-out/` and `.ai/*`. Shared on purpose: `.claude/settings.json` (project plugin opt-ins), `.serena/project.yml` (Serena language config), `.ai/enabled` (opt-ins and opt-outs) and `.omc/skills/`; `.claude/commands/` and `.claude/agents/` only when the repo already tracks them.

Both blocks are committed and pushed, so they never hold secrets or personal data: ai-adopt scans them before its commit and the secret-scan gate scans every agent commit. Worked example with costs: [README.md](../README.md), section 3, example D.

### matt grilling vs OMC deep-interview

Both ask questions before work. Grilling is short: numbered rounds, a recommended answer for each, no action until you confirm. Deep-interview is long: it scores ambiguity and gates execution. We use grilling for kickoff and "grill me", and deep-interview only when you say "deep interview".

### claude-blog vs claude-seo

Nine pairs of skills overlap in name (schema, GEO, brief, cluster, flow, google, strategy, image, discourse). One question decides: is the input one post file or a live URL/site? Post file means blog. URL or site means seo. Image tasks: ask first. `blog-image` for a post, `seo-image-gen` for site assets, ui-ux-pro-max `banner-design` only for ads and social banners.

### RTK vs other Bash hooks

RTK rewrites the command text (`git status` becomes `rtk git status`). Our gates read the command text too. Our regexes use word boundaries so a leading `rtk` does not hide a command. Our gates are placed before RTK where the order is configurable. Security tools (agent-audit, gitleaks, osv-scanner) run through `rtk bypass` so findings are never truncated. Serena's and graphify's hooks add advice, not rewrites.

### Ponytail vs OMC

OMC has a skill, `minimal-code-discipline`, with the same job as Ponytail. Ponytail owns the global rule. Do not run both on the same task.

### i-have-adhd vs caveman (dropped)

Both shorten replies. We dropped caveman: it overlaps i-have-adhd and the "Reporting style" of the root rules. One reply style only. Since 2026-11-14 `install.sh` removes it (plugin, its marketplace, its two settings.json hooks, the `caveman-shrink` MCP server in Claude and Codex), saves each entry and records a restore. Its hook scripts in `~/.claude/hooks/` stay and are reported.

### Other dropped or not adopted

The context7 plugin is dropped (the MCP does the same). `byterover-mcp` is dropped (its endpoint is gone): removed from Claude and Codex. `typesafe@typesafe-ai` stays installed but off at user scope. The lists are in `ai/pins.env` (`AI_DROP_*`, `AI_OFF_CLAUDE_PLUGINS`): a later drop is one word there. Not adopted: superpowers (a second kickoff, clashes with OMC), Docker Dynamic MCP, Smithery, MetaMCP, Nix tools, sfw (forced telemetry), context7 On-Premise, an LLM classifier router.

## 6. How they interact

One chain, from prompt to proof.

1. **The prompt.** You type "write a post about X for my site".
2. **Router (L3 and L2).** The regex rules match. The tie-break says: a post file, so `claude-blog:blog`, not `seo-*`. The hook adds a forced-evaluation text. The agent answers YES for claude-blog.
3. **The skill fires.** The agent calls the `Skill` tool with `claude-blog:blog`. A PostToolUse hook records it in `~/.local/state/ai/fired.jsonl`. A typed `/skill` is recorded the same way (UserPromptExpansion).
4. **Other tools join.** While writing, Ponytail keeps diffs small, i-have-adhd keeps replies short, RTK shortens command output. If the post needs a library fact, the context7 server instructions point to context7 with the cached ID.
5. **Gates.** If the agent runs `npm install`, the audit gate checks `audit.log`. If it commits, the secret gate scans.
6. **Stop.** When the turn ends, the Stop hook compares: which rules fired, and did a matching tool or skill call follow (the `proof` regex of each rule)? If not, it writes a line to `~/.local/state/ai/misses.jsonl`.
7. **ai-doctor.** It reads the miss log and the gate log of the last 7 days. It also checks that each tool still has its contract and that the versions equal the pins. A rule that misses often needs a better regex, a clearer skill description, or an eval.

So: router nudges, skill fires, proof is logged, a miss is logged, `ai-doctor` reports it, and you fix the rule. See [docs/EXTENDING.md](EXTENDING.md) for how.

Known gaps: opencode has no hooks, so only the root rules apply there. Hermes has no per-prompt skill matching, so a small plugin does L2 and L3. Skills that only you can type (`grill-me`, `wait-what`, `retro`, `i-have-adhd`) cannot be forced: the agent suggests them.

## 7. Defaults and configuration

One row per tool: is it on, where we configure it, the exact settings, why, and what it costs in tokens. "Server" means a Linux install (`install.sh --for-user`); the Mac keeps its own defaults where a row says so. Token costs are first-call input tokens of a fresh Claude session, measured in the Fable readiness audit (2026-11-12) where a number is given; "deferred" means Claude loads the tool schemas only when it searches for them.

| Tool | Default | Where configured | Exact settings | Why | Token cost | Source |
|---|---|---|---|---|---|---|
| RTK 1.2.0 | on (Claude, Codex) | Claude: `hooks/rtk-hook` of ai-core runs `rtk hook claude`, but not in auto mode (Mac: `~/.claude/settings.json`; server: managed-settings `hooks.PreToolUse` with `/usr/local/bin/rtk`); Codex: `/etc/codex/hooks.json`; RTK: `~/.config/rtk/config.toml` (macOS: `~/Library/Application Support/rtk/config.toml`) | `[hooks] exclude_commands = ["git push", "gh"]`; telemetry off by env `RTK_TELEMETRY_DISABLED=1`; tracking and the local sqlite retriever stay at RTK's defaults (local only) | Shorter command output. It rewrites git, gh, cargo, npm, pnpm, npx, bun, uv, pip, cat/head/tail, grep, rg, ls, find, tree, diff, curl, wget, pytest, mypy, ruff, go, docker, kubectl and more (`src/discover/rules.rs`). `git push` and `gh` are excluded: they must leave the sandbox as the exact absolute command the router writes. The gates see through `rtk` and `rtk proxy` | saves output tokens; check with `rtk gain` | https://github.com/rtk-ai/rtk/blob/v1.2.0/docs/guide/getting-started/configuration.md |
| context7 MCP 4.6.0 | on (Claude, Codex, Hermes) | ai-core `.mcp.json` (`mcp/context7.sh`); key from `~/.config/ai/secrets.env` or the committed free key | pinned npm package under `~/.local/share/ai/npm`, no runtime npx; library IDs live in the repo AGENTS.md Libraries section (`ai-libs`); default client timeouts | Current library docs at the right version | deferred, near zero idle | https://github.com/upstash/context7 |
| box MCP (ai-box) | on, profile server only (dev-mac: not installed) | ai-box `.mcp.json` `box`: `/usr/bin/python3 -I mcp/box.py`; Claude `timeout` 3720000 ms; Codex `tool_timeout_sec = 3720`, `default_tools_approval_mode = "approve"` | talks to `/run/proj-agent.sock`; output cut at 40k characters per stream; exec up to 3600 s | Box work from a sandbox without opening unix sockets | deferred; zero tools without proj-agent | `ai/marketplace/plugins/ai-box/mcp/box.py`, ubuntu-server `docs/NOTES.md` (socket protocol v1) |
| Serena 2.1.0 | **on in every project** (Claude, Codex, Hermes); a project opts out with `no-serena` in `.ai/enabled` | `~/.serena/serena_config.yml`; Claude: plugin `ai-serena@ai` on at user scope; Codex: `[mcp_servers.serena]`; Hermes: `mcp_servers.serena` | `start-mcp-server --project-from-cwd --context=claude-code` (Codex `codex`, Hermes `ide`), `SERENA_USAGE_REPORTING=false`; `agent_interface: tools`, `excluded_tools: [execute_shell_command, serena_repl]`, `web_dashboard: false`, `gui_log_window: false`, `log_level: 30`, `tool_timeout: 240`, `default_max_tool_answer_chars: 40000`, `default_modes: [no-memories]`; Codex `startup_timeout_sec = 60`, `tool_timeout_sec = 300`; `ai-adopt` runs `serena project create --index` | Symbol reads, references and edits without reading whole files. The claude-code context already drops Serena's file and shell tools (Claude has them). No memories and no onboarding: the AGENTS.md Map is the one place for project knowledge; onboarding is a long first-run exploration that writes a second copy that drifts. Not used: the `cc_system_prompt_override` (its rule table forbids Read and Edit outright and conflicts with our navigation order), `serena-hooks remind` (false denials, issues #2251 and #2204; it also fights graphify's nudges). Claude: `alwaysLoad: true` in the ai-serena plugin, so agents see the Serena tools from the first turn (owner 2026-11-16; ai-doctor checks it) | all Serena schemas on every turn | https://github.com/oraios/serena/tree/v2.1.0 (`serena_config.template.yml`, `contexts/`, `modes/no-memories.yml`) |
| graphify 0.9.105 | **on in every project** (code only, no key); opt out with `no-graph` | env `GRAPHIFY_BACKEND=none`, `GRAPHIFY_HOOK_STRICT=0`; `ai-adopt`: `graphify extract . --code-only`, `graphify hook install`; allow list: `graphify query/path/explain/extract/update` | git hooks post-commit, post-checkout, post-merge, post-rewrite rebuild the graph in the background; its global CLAUDE.md/AGENTS.md install and its PreToolUse hooks are not used (removed if found) | Structure questions ("where is X, what depends on Y") from a local graph. The CLI is the query path: its MCP server (`graphify.serve`) needs the extra `mcp` dependency and adds about ten tool schemas | zero (CLI) | https://github.com/Graphify-Labs/graphify (0.9.105 wheel: `hooks.py`, `serve.py`) |
| Ponytail 5.3.3 | on (Claude, Codex) | audited clone in `/opt`, Claude plugin; `~/.config/ponytail/config.json` | `defaultMode: "full"` | Smaller diffs | about 1.6k | https://github.com/DietrichGebert/ponytail |
| i-have-adhd 0.4.1 | on (Claude, Codex) | audited clone, Claude plugin; flag file `~/.claude/.i-have-adhd-always` | always-on mode | Short answers (owner choice) | about 2.4k | https://github.com/ayghri/i-have-adhd |
| mattpocock skills | on (5 skills) | pinned commit, linked into `~/.agents/skills` | grilling, grill-me, wait-what, retro, writing-for-agents | Interview and review habits | small (skill descriptions) | https://github.com/mattpocock/skills |
| herdr 0.9.5 | on, every machine | audited installer to `/usr/local/bin/herdr`; `~/.config/herdr/config.toml` | `[update] version_check = false`, `manifest_check = false`; `herdr integration install` per agent | Owner tool for watching agent sessions ("leave it alone") | none in the model context | https://herdr.dev (installer pinned by sha256 in `ai/pins.env`) |
| oh-my-claudecode 5.8.4 | server: installed, OFF at user scope (the owner turns it on per project with `ai-adopt --tools omc`); macOS: on | Claude plugin `oh-my-claudecode@omc`; `~/.config/claude-omc/config.jsonc` | `security.disableAutoUpdate = true`, `mcpServers.exa.enabled = false` | Multi-agent workflows when wanted. Inside an OMC session our managed policy still applies: the sandbox, the managed deny rules and the managed router hooks run for every tool call, also in its subagents (hooks receive subagent calls; settings are per process). Nothing extra is injected | about 6.7k when on | https://github.com/Yeachan-Heo/oh-my-claudecode |
| claude-seo 2.5.0, claude-blog 2.3.2 | opt-in per project | Claude plugins, off at user scope; `ai-adopt --tools seo,blog` | none | Large skill sets for SEO and blog work | about 12k each when on | https://github.com/AgriciDaniel/claude-seo, https://github.com/AgriciDaniel/claude-blog |
| ui-ux-pro-max, typesafe | off at user scope where installed (not installed by this setup) | `AI_OFF_CLAUDE_PLUGINS` in `ai/pins.env`; ui-ux-pro-max per project: `ai-adopt --tools ui` | enabledPlugins false | Skill listings cost tokens in every session | zero when off | owner decision 2026-11-14 |
| last30days 3.39.0 | on (Claude) | Claude plugin `last30days@last30days-skill`, newest stable tag; `~/.config/last30days/.env` (optional keys) | enabledPlugins true; no key needed | Recent opinion and trends from social and market sources | skill description about 70; no hook since v3.39.0 | https://github.com/mvanhorn/last30days-skill |
| Playwright MCP 0.0.85 | opt-in per project | plugin `ai-playwright@ai` (off at user scope); `ai-adopt --tools browser` | `ai-playwright-mcp --headless --isolated`, pinned, no npx | Browser checks only where a project needs them | deferred when on | https://github.com/microsoft/playwright-mcp |

Navigation order for agents (rules): AGENTS.md Map, then `graphify query` for structure, then Serena symbol tools for definitions, references and edits, then a narrow `rg` and reading only the lines found.

## 8. Overlaps: one job each

| Area | Who does it | Duplicates and what we did |
|---|---|---|
| Navigation | 1 AGENTS.md Map (what lives where), 2 `graphify query` (structure, dependencies), 3 Serena symbol tools (definitions, references, symbol edits), 4 built-in Grep/Read on the located lines | Serena's file and shell tools are off (claude-code context; `excluded_tools: execute_shell_command, serena_repl`). OMC `lsp_*` / `ast_grep_*`: OMC is off on servers; where it is on, rules say Serena first. No Claude LSP plugin is installed. graphify MCP not installed (CLI only) |
| Hooks: SessionStart | router (one status line; the skill card; the sessions line), i-have-adhd, Ponytail, OMC (when on), Serena `activate` for Codex only | Serena `activate` skipped for Claude (single-project context). graphify's global hooks removed |
| Hooks: PreToolUse | RTK rewrites (Bash; Claude: not in auto mode); router gates (Bash, Edit, Write, Skill) and absolute rewrite of excluded commands | No two rewrites of one command: RTK excludes `git push` and `gh`. Deny wins over any rewrite. Serena `remind` and graphify `hook-guard` not installed |
| Hooks: Stop, SessionEnd, Notification | router, claude-notify, `stop-check` (check-fast), OMC persistent mode (when on), Serena `cleanup` | stop-check is silent while an OMC persistent mode of the session is active; OMC never blocks a continuation stop: one stop never gets a block from both |
| Git hooks | graphify post-commit/checkout/merge/rewrite (owner's own git) | The server git guard turns them off for agent git calls |
| Instructions | managed CLAUDE.md and AGENTS.md (one render of `ai/agents-md/`), rules files per tool | Serena's system-prompt override not used; graphify's CLAUDE.md/AGENTS.md section not installed |
| Memory | facts about the repo: AGENTS.md Map and Libraries (the repo is the one knowledge store; Claude auto memory is off) | Serena memories off (mode `no-memories`); OMC project memory only where the owner turns OMC on |
| Library docs | context7 only | Grounded Docs and the GitHub MCP dropped |
| Skills that overlap (OMC and OMX add about 85 and 24 skills) | the `winners` table in `ai/routing.yaml` (section 5 of the skills guide as data) | A Skill call of a loser is denied with the winner's name (`winner-gate`). OMC and OMX win orchestration: `autopilot`, `ralph`, `team` and `ultragoal` unlock the losers for the session. `skillOverrides` cannot hide plugin skills, so a gate does it |
