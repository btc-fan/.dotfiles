# Tools and agents

Every tool in the setup: what it is, why we chose it, how it works here, and what to do when two tools overlap.
Each entry ends with the link to its usage contract in `ai/rules/`. The contract is the exact rule set. This page is the explanation.

Words used below:
- **Global**: installed on every machine, active in every project.
- **Opt-in**: only in a project that asked for it (`ai-start` or `ai-adopt` writes the project layer).
- **Pin**: the exact version or commit that was audited. All pins are in `ai/pins.env`.
- **Contract**: `ai/rules/<tool>.md`. Sections: vendor rules, when and when not, enforcement, proof, setup.

## Contents

1. [Agents and harnesses](#1-agents-and-harnesses)
2. [MCP servers](#2-mcp-servers)
3. [Plugins, skills and CLI tools](#3-plugins-skills-and-cli-tools)
4. [Audit and safety tools](#4-audit-and-safety-tools)
5. [Overlaps and how we decide](#5-overlaps-and-how-we-decide)
6. [How they interact](#6-how-they-interact)

## 1. Agents and harnesses

An agent is the program that talks to a model and runs tools. A harness is an agent plus extras that orchestrate it.

### Claude Code (with oh-my-claudecode)

- **What.** Anthropic's coding agent in the terminal. oh-my-claudecode (OMC) adds a workflow on top: plan, execute, review, verify, plus team runs and loops. It is installed as a pinned Claude plugin (`oh-my-claudecode@omc`, tag v5.8.4, commit checked), on servers too (owner decision 2026-11-12). The old npm route (`oh-my-claude-sisyphus`) stays available with `AI_OMC_WIRING=cli`.
- **Why.** It is the main agent. It has the richest hook system, which the router and the gates need.
- **How it works here.** The plugin `ai-core` is installed from our local marketplace `ai`. Claude reads the root rules through an `@import` line in a managed block of `~/.claude/CLAUDE.md`. Example: you type "autopilot: build a CSV to JSON tool". OMC's own keyword hook starts its autopilot skill and writes state to `.omc/state/`. Our rules still win on a clash: the 60-word reply limit and the confirm-first rules beat OMC defaults.
- **Scope.** Global, main.
- **Pin.** OMC 5.8.4 (`OMC_VERSION`, sha512 in `pins.env`). Claude Code comes from the signed apt repository on Ubuntu.
- **claude.ai connectors off on servers.** The account connectors (Gmail, Calendar, Drive and the like) do not load in Claude Code on Linux installs (`disableClaudeAiConnectors` and `ENABLE_CLAUDEAI_MCP_SERVERS=false`), so an unattended agent cannot reach your mail. macOS keeps Claude's default. To keep them on a server: `install.sh --keep-claudeai-connectors` (see [INSTALL.md](INSTALL.md)).
- **Telemetry and updates off.** Managed settings (`/etc/claude-code/managed-settings.json` on Ubuntu): telemetry, error reports and auto-updater off. OMC: `{"security":{"disableAutoUpdate":true}}` and the exa web-search MCP off (`mcpServers.exa.enabled: false`) in its config, and `OMC_UPDATE_REGISTRY_BASE` pointed at a dead local address (its daily npm ping ignores the setting). `OMC_REPLY_ENABLED` is never set.
- **Contract.** `ai/rules/omc.md`.

### Codex (with oh-my-codex)

- **What.** OpenAI's coding agent. oh-my-codex (OMX) is the OMC-like layer for Codex.
- **Why.** A second main agent: a second model family, and a way to cross-check Claude.
- **How it works here.** Codex cannot `@import`. It gets a managed block `AI:core` copied into `~/.codex/AGENTS.md`. `ai-sync` refreshes the copy after each `git pull`. The same `ai-core` plugin installs into Codex from the same folder, so the router and gates run there too. Codex asks once to trust the plugin hooks (`/hooks`). Example: `omx exec "<prompt>"` runs a non-interactive Codex task.
- **Scope.** Global, main. OMX is held until 2026-11-17 (`OMX_NOT_BEFORE`), because the audited release was under one day old at intake.
- **Pin.** Codex 0.167.0, OMX 0.22.6.
- **Telemetry and updates off.** Codex analytics, feedback and update checks off in `config.toml`. `OMX_AUTO_UPDATE=0`, `OMX_NATIVE_AUTO_FETCH=0`. No native binaries.
- **Warning.** The OMX template says "do not stop to ask, proceed". The root rules say the owner's confirm-first rules win. Never run OMX in a Claude session.
- **Contract.** `ai/rules/omx.md`.

### opencode

- **What.** An open-source terminal agent that talks to many model providers.
- **Why.** It is the front-end for other models (Grok, Kimi, DeepSeek) and a fallback. Always installed.
- **How it works here.** It reads the root rules through the `instructions` key of `~/.config/opencode/opencode.json`. It reads the shared skills folder `~/.agents/skills`. It has no hooks, so no gates and no miss log inside it: only the root rules apply. Example: `opencode run "<prompt>" --format json`.
- **Scope.** Global, always installed.
- **Pin.** 1.19.5 (closed binary, audited). Never run `opencode upgrade`.
- **Telemetry and updates off.** `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_MODELS_FETCH=1`, `OPENCODE_DISABLE_LSP_DOWNLOAD=1`, and `{"autoupdate":false,"share":"disabled"}` in its config.
- **Contract.** `ai/rules/opencode.md`.

### Hermes

- **What.** A chat-gateway agent (Discord) with a daily summary.
- **Why.** You can talk to the server from your phone.
- **How it works here.** It runs as its own user `hermes`. Every change to it is made as that user and recorded in its own state file. Root rules go into a managed block of its `SOUL.md`, refreshed by `ai-sync`. A small plugin does the L2 and L3 routing. It uses plain skills only. SEO and blog work goes to Claude Code (`claude -p`, never `--bare`). Only the owner's Discord id may talk to it.
- **Scope.** Global, configured (Linux server).
- **Pin.** No installer pin exists. The version after install is recorded in `pins.env`.
- **Telemetry off.** Yes, in its config. Approvals stay manual.
- **Contract.** `ai/rules/hermes.md`.

### herdr

- **What.** A terminal multiplexer for agents: several agents in panes, with status and session ids.
- **Why.** It gives us the session ids that the PR "author-sessions" block needs, and a status view.
- **How it works here.** `herdr integration install claude|codex` adds status hooks. The agent reads its own session id with `herdr agent get "$HERDR_PANE_ID"`. The `pr-rules` gate blocks a PR body without the author-sessions block. `pr-resume` reads that block later to resume the sessions. herdr is not a harness: it makes no model call.
- **Scope.** Global, configured.
- **Pin.** 0.9.5. The installer has no checksum: we pin the installer's sha256 and read it before use.
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

MCP servers give agents extra tools, and each one costs context in every session, so the global list is short: only context7, from `ai/marketplace/plugins/ai-core/.mcp.json` (tool names `mcp__plugin_ai-core_context7__*`). Per project: Serena through the plugin `ai-serena@ai` (off at user scope, on with `enabledPlugins` in the project settings), Playwright through the plugin `ai-playwright@ai` (same mechanism, `ai-adopt --tools browser`). Managed settings block servers from a project `.mcp.json` (a planted file in a workspace must not start a process).

### context7

- **What.** A cloud service with current docs for libraries, exposed as two MCP tools. The one docs tool (owner decision 2026-11-12: Grounded Docs dropped).
- **Why.** Training data is old. Docs in a tool call beat answers from memory.
- **How it works here.** The repo AGENTS.md has a "## Libraries" section with a context7 ID per library (written by `ai-libs --sync`). A cached ID means `query-docs` directly, no `resolve-library-id`. Otherwise `resolve-library-id`, then `query-docs`, one concept per call, at most 3 calls. Queries leave the machine, so no secrets and no private code in a query. Free plan: 1,000 calls per month; cached IDs save about half. `ai-libs` sends only public package names, once per library, and nothing at all for an ecosystem with a private index. The free key is committed in the plugin config (owner decision, one allowlisted exception to the secret scan).
- **Scope.** Global.
- **Pin.** `@upstash/context7-mcp@4.6.0`.
- **Contract.** `ai/rules/context7.md`.

### Serena (opt-in per project)

- **What.** A code-intelligence server. It reads and edits code by symbol through language servers.
- **Why.** On a big repo, a symbol lookup costs far fewer tokens than reading files, and edits by symbol are exact. On small projects the Map plus rg is enough, so it is off by default (owner decision 2026-11-12; the old global "Serena first" nudge was ignored in the logs).
- **How it works here.** `ai-adopt --tools serena` turns on the plugin `ai-serena@ai` for that project (`enabledPlugins` in the project `.claude/settings.json`; the plugin holds only the Serena MCP entry and is off at user scope), writes a Codex entry in `.codex/config.toml` (trusted projects only), and indexes the project. Hermes and opencode get no Serena. There: `get_symbols_overview`, `find_symbol`, `replace_symbol_body`. No memories by default: project knowledge lives in AGENTS.md.
- **Pin.** `serena-agent==2.1.0`. **Telemetry off.** `SERENA_USAGE_REPORTING=false` in the server entry's `env`.
- **Contract.** `ai/rules/serena.md`.

### GitHub: the `gh` CLI

- **What.** GitHub work (issues, pull requests, reviews) goes through `gh`. The GitHub MCP is dropped (owner decision 2026-11-12: a large tool list and a full-access token).
- **How it works here.** Read-only by default. Writes (a PR, a comment, a merge) are outward actions: confirm first; a PR goes through the `pr-rules` gate. owner/repo comes from the origin remote.

### Playwright MCP

- **What.** A browser the agent can drive: open a page, click, take a screenshot.
- **Why.** End-to-end checks and screenshots. The vendor itself says CLI skills are cheaper than an always-on MCP, so we do not keep it always on.
- **How it works here.** Opt-in per project. `ai-adopt --tools browser` turns on the plugin `ai-playwright@ai` for that project (and writes the Codex project config), headless and isolated. Outside such a project, the rule `browser-not-enabled` tells the agent to suggest `ai-adopt --tools browser`. The agent must not install a browser tool itself.
- **Scope.** Opt-in per project.
- **Pin.** `@playwright/mcp` 0.0.85.
- **Contract.** `ai/rules/playwright.md`.

## 3. Plugins, skills and CLI tools

### graphify (opt-in per project)

- **What.** Builds a code graph of a repo: which file calls which. Local, no LLM for code.
- **Why.** "What calls Y" on a big, unfamiliar codebase. Off by default: unproven benefit on small projects.
- **How it works here.** `ai-adopt --tools graph` runs `GRAPHIFY_BACKEND=none graphify extract . --code-only` (no key, nothing sent out; bare `graphify .` asks for an LLM key and fails, so never use it) and gitignores `graphify-out/`. There: `graphify query "..."`, and `graphify update .` after code changes. No git hook by default; optional owner step: `graphify hook install`.
- **Pin.** 0.9.105 (PyPI `graphifyy`). **Telemetry.** None documented.
- **Contract.** `ai/rules/graphify.md`.

### RTK (Rust Token Killer)

- **What.** A command proxy that shortens the output of shell commands (git, test runs, logs) before the agent reads it.
- **Why.** Output is the biggest token cost in a coding session. Savings are up to 90%.
- **How it works here.** A hook rewrites `git status` to `rtk git status`. The agent does not call it by hand. Exception: `uv run` is not rewritten, so in a Python project the agent types `uv run rtk pytest`. For security tools and debugging use `rtk bypass <cmd>` so findings are not cut. Check with `rtk gain --history`.
- **Scope.** Global, on by default.
- **Pin.** v1.2.0, built from source (`cargo --locked`).
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
- **How it works here.** Enabled per project, never in the user settings. Logo, icon and image generation call a paid API: ask first. Never copy its `stack/` folder.
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

### Toolbox (not installed)

Good tools that are not part of daily work live in `ai/TOOLBOX.md`. They are not loaded into sessions. The root rules have one pointer line. Each needs a full audit before its first install.

## 4. Audit and safety tools

### agent-audit

- **What.** Our wrapper: `agent-audit npm|pypi|dir|skill <target>`. It runs guarddog (malware rules), osv-scanner (known vulnerabilities) and a skill scanner.
- **Why.** Every tool, package, MCP server, skill and plugin is checked before it runs.
- **How it works here.** Each run appends `<time> <ecosystem> <name> <version> PASS|FAIL` to `~/.local/state/ai/audit.log`. The install gate reads that file. A missing scanner counts as a finding (fail closed). A FAIL means stop and show the owner.
- **Example.** `agent-audit pypi graphifyy` before `uv tool install graphifyy==0.9.105`.

### gitleaks

- **What.** A secret scanner.
- **Why.** The `secret-scan` gate runs it next to our own patterns, when it is installed.
- **Pin.** 8.30.1, proposed: its audit is still owed.

### ai-doctor

- **What.** The health check for the whole setup.
- **How it works here.** It validates the plugin, tests the router with sample inputs, checks every enabled tool has a contract, compares the copied rule blocks to the source, and reads the miss log. `ai-doctor --quick` runs at the end of the install.

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
| Code lookup | the Map in AGENTS.md, then rg / Grep | Serena or graphify (only where turned on), OMC `lsp_*` | One default path; extra tools per project. |
| Library API docs | context7 with the ID from the Libraries section | web search | Cached ID first, web last. |

### Finding code: Map, rg, then opt-in tools

- Default in every repo: read the Map section of AGENTS.md (no tool call), then one narrow `rg` / Grep, then read only the located lines.
- Serena (symbols) and graphify (call graph) only in projects that turned them on, for big repos or heavy refactors.
- OMC `lsp_*` and ast-grep: fallback, for diagnostics or a language Serena does not cover.
Example: "who calls `calc_price`?" starts with the Map (which module), then `rg -n "calc_price(" src/`, then a read of three lines.

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
| Where things live, how to run and test, conventions | "## Map" in the repo AGENTS.md (managed block, <= 60 lines, committed) | ai-adopt (facts from the repo, plus one read-only claude pass for conventions) | a commit adds, deletes or renames modules (`knowledge-check` says so); `ai-adopt --refresh-map` |
| Library versions and context7 IDs | "## Libraries" in the repo AGENTS.md (managed block, committed) | `ai-libs --sync` | lockfile changes or a new ID was used |
| Code structure (opt-in) | `graphify-out/` (gitignored) | `ai-adopt --tools graph` | `graphify update .` |
| Session notes | OMC notepad | the agent | never project truth |

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

Both shorten replies. We dropped caveman: it overlaps i-have-adhd and the "Reporting style" of the root rules. One reply style only.

### Other dropped or not adopted

The context7 plugin is dropped (the MCP does the same). Not adopted: superpowers (a second kickoff, clashes with OMC), Docker Dynamic MCP, Smithery, MetaMCP, Nix tools, sfw (forced telemetry), context7 On-Premise, an LLM classifier router.

## 6. How they interact

One chain, from prompt to proof.

1. **The prompt.** You type "write a post about X for my site".
2. **Router (L3 and L2).** The regex rules match. The tie-break says: a post file, so `claude-blog:blog`, not `seo-*`. The hook adds a forced-evaluation text. The agent answers YES for claude-blog.
3. **The skill fires.** The agent calls the `Skill` tool with `claude-blog:blog`. A PostToolUse hook records it in `~/.local/state/ai/fired.jsonl`. A typed `/skill` is recorded the same way (UserPromptExpansion).
4. **Other tools join.** While writing, Ponytail keeps diffs small, i-have-adhd keeps replies short, RTK shortens command output. If the post needs a library fact, `docs-lookup` points to context7 with the cached ID.
5. **Gates.** If the agent runs `npm install`, the audit gate checks `audit.log`. If it commits, the secret gate scans.
6. **Stop.** When the turn ends, the Stop hook compares: which rules fired, and did a matching tool or skill call follow (the `proof` regex of each rule)? If not, it writes a line to `~/.local/state/ai/misses.jsonl`.
7. **ai-doctor.** It reads the miss log and the gate log of the last 7 days. It also checks that each tool still has its contract and that the versions equal the pins. A rule that misses often needs a better regex, a clearer skill description, or an eval.

So: router nudges, skill fires, proof is logged, a miss is logged, `ai-doctor` reports it, and you fix the rule. See [docs/EXTENDING.md](EXTENDING.md) for how.

Known gaps: opencode has no hooks, so only the root rules apply there. Hermes has no per-prompt skill matching, so a small plugin does L2 and L3. Skills that only you can type (`grill-me`, `wait-what`, `retro`, `i-have-adhd`) cannot be forced: the agent suggests them.
