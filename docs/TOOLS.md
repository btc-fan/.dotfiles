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

MCP servers give agents extra tools. Ours come from one file, `ai/marketplace/plugins/ai-core/.mcp.json`, so Claude and Codex see the same list. Tool names look like `mcp__plugin_ai-core_<server>__<tool>`.

### Serena

- **What.** A code-intelligence server. It reads and edits code by symbol (function, class) through language servers.
- **Why.** Reading a symbol costs far fewer tokens than reading a file, and edits by symbol are exact.
- **How it works here.** Session start: `initial_instructions`, then `read_memory core`. Core is the project's entry memory: a source map, the main commands, links to the other memories. Then the agent calls `get_symbols_overview`, then `find_symbol` with the body, and edits with `replace_symbol_body`. Example: "rename `calc_price`" means `find_referencing_symbols`, then `rename_symbol`. Line numbers start at 0. A router nudge (`serena-first`) reminds the agent when it reads code with `cat` or Read. It only reminds. It never blocks.
- **Memories.** `.serena/memories/` in the repo, committed. Serena onboarding writes them once (ai-adopt runs it in its own headless session). One global file, `global/memory_maintenance`, tells every agent how to write them: dense notes, size caps, no secrets or personal data. After a commit that moves modules, the router asks the agent to fix the source map in core.
- **Scope.** Global.
- **Pin.** `serena-agent==2.1.0`.
- **Telemetry off.** `SERENA_USAGE_REPORTING=false` in the server entry's `env`. The web dashboard is off.
- **Contract.** `ai/rules/serena.md`.

### context7

- **What.** A cloud service with current docs for libraries, exposed as two MCP tools.
- **Why.** Training data is old. It is the fallback when Grounded Docs lacks a library.
- **How it works here.** The agent looks in `.ai/libs.md` first. A cached ID means `query-docs` directly, no `resolve-library-id`. Otherwise `resolve-library-id`, then `query-docs`, one concept per call, at most 3 calls. Queries leave the machine, so no secrets and no private code in a query. Free plan: 1,000 calls per month; cached IDs save about half. The free key is committed in the plugin config (owner decision, one allowlisted exception to the secret scan).
- **Scope.** Global.
- **Pin.** `@upstash/context7-mcp@4.6.0`.
- **Contract.** `ai/rules/context7.md`.

### Grounded Docs

- **What.** A self-hosted docs server (`@arabold/docs-mcp-server`). You index library docs once. Agents search them.
- **Why.** Local, private and fast. Nothing leaves the network.
- **How it works here.** It runs once on the server, on port 6280, reachable from the LAN and the private network only. Clients use read-only tools: `search_docs` with the name and version from `.ai/libs.md` (`list_libraries` only when the name is not cached). Scraping new docs is a server task for the owner; `ai-libs --sync` prints the libraries that are not indexed yet.
- **Scope.** Global. It is the first choice for library docs.
- **Pin.** 3.4.1.
- **Telemetry off.** `DOCS_MCP_TELEMETRY=false` (the vendor default sends to PostHog). Clients set `DOCS_MCP_READ_ONLY=true`.
- **Contract.** `ai/rules/grounded-docs.md`.

### GitHub MCP

- **What.** GitHub's official MCP server: issues, pull requests, reviews.
- **Why.** Structured access instead of parsing `gh` output.
- **How it works here.** Full access, by owner decision. Pushes, merges and issue edits are outward actions, so the root rules say: confirm first. The token is read from `~/.config/ai/secrets.env` by a small wrapper. Not for local git: use git.
- **Scope.** Global.
- **Pin.** v2.1.0, release checksums in `pins.env`.
- **Contract.** `ai/rules/github-mcp.md`.

### Playwright MCP

- **What.** A browser the agent can drive: open a page, click, take a screenshot.
- **Why.** End-to-end checks and screenshots. The vendor itself says CLI skills are cheaper than an always-on MCP, so we do not keep it always on.
- **How it works here.** Opt-in per project. `ai-start` or `ai-adopt` writes it into that project's `.mcp.json` (and the Codex project config), headless and isolated. Outside such a project, the rule `browser-not-enabled` tells the agent to ask you to run `ai-start`. The agent must not install a browser tool itself.
- **Scope.** Opt-in per project.
- **Pin.** `@playwright/mcp` 0.0.85.
- **Contract.** `ai/rules/playwright.md`.

## 3. Plugins, skills and CLI tools

### graphify

- **What.** Builds a knowledge graph of a code repo: which file calls which, how parts connect. Local, no LLM for code.
- **Why.** "Where is X" and "what calls Y" are answered from the graph, not by reading many files.
- **How it works here.** `GRAPHIFY_BACKEND=none graphify extract . --code-only` once per repo (ai-adopt runs it). It needs no key and sends nothing out. Bare `graphify .` is the skill form: headless it asks for an LLM key and fails, so we never use it. Then `graphify query "where is the price calculated"`. After code changes and after `git pull`, `graphify update .` (no cost). No graphify git hook by default (the router's post-commit nudge covers it); optional owner step per repo: `graphify hook install`. Its own hook only advises. The environment also sets `GRAPHIFY_BACKEND=none`.
- **Scope.** Global.
- **Pin.** 0.9.105 (PyPI `graphifyy`).
- **Telemetry.** None documented. Cloud and ingest features are not used.
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
| Code symbol lookup or edit | Serena | OMC `lsp_*` | lsp is the fallback. |
| Library API docs | `.ai/libs.md` IDs, then Grounded Docs | context7, then web | Cached first, local second, cloud third, web last. |

### graphify vs Serena vs OMC lsp

Three tools can answer "where is this code". They do different parts.
- graphify finds: structure, "where is X", "what calls Y". Think map.
- Serena reads and edits: symbols and their callers. Think scalpel.
- OMC `lsp_*` and ast-grep: fallback, when Serena has no language server for the file, or for diagnostics.
Order: Serena memory core first (once per session), then graphify, then Serena symbols, then read only the lines they located. Built-in Read and Edit are for non-code files (md, json, yaml, toml, env, lock files). Example: "who calls `calc_price`?" starts with `graphify query`, then `find_referencing_symbols` for the exact list, then a read of three lines.

### Grounded Docs vs context7 vs web

- Step 0: `.ai/libs.md` (version, context7 ID, Grounded Docs name; no call at all).
- Step 1: Grounded Docs (local, private, indexed by the owner).
- Step 2: context7 (cloud, current, 1,000 calls a month, queries leave the machine). Skip `resolve-library-id` when the ID is cached.
- Step 3: library source or the official site, and say that docs were not found.
Use the project's version. Never send secrets or private code in a docs query. Web search is not a docs tool: Codex too uses context7 first.

### Where project knowledge lives (one home per fact)

The goal: an agent never explores a repo from zero. Each kind of fact has one home, one way to read it, and one trigger to refresh it.

| Fact | Home | Made by | Read with | Refreshed when |
|---|---|---|---|---|
| Behaviour rules | AGENTS.md (short) | ai-render, ai-adopt | loaded every session | rules change |
| Code map, commands, conventions | `.serena/memories/` (committed) | Serena onboarding, run by ai-adopt | `read_memory core` | a commit adds, deletes or renames modules (row `knowledge-check`) |
| Code structure | `graphify-out/` (generated, gitignored) | ai-adopt | `graphify query` | `graphify update .` after code changes or `git pull` |
| Library versions and docs IDs | `.ai/libs.md` (committed) | `ai-libs --sync` | the agent, and the docs rows show the cached IDs | lockfile changes or a new ID was used |
| Session notes | OMC notepad | the agent | the agent | never kept as project truth |

Rules that keep it honest: the session start line shows memory count and three freshness flags (memories, graph, docs map). No memory text is injected: the agent reads core on purpose. Memories are hints, the code wins. Memories and libs.md are committed and pushed, so they never hold secrets or personal data: the secret-scan gate and ai-adopt scan them. Worked example with costs: [README.md](../README.md), section 3, example D.

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
4. **Other tools join.** While writing, Ponytail keeps diffs small, i-have-adhd keeps replies short, RTK shortens command output. If the post needs a library fact, `docs-lookup` points to Grounded Docs first.
5. **Gates.** If the agent runs `npm install`, the audit gate checks `audit.log`. If it commits, the secret gate scans.
6. **Stop.** When the turn ends, the Stop hook compares: which rules fired, and did a matching tool or skill call follow (the `proof` regex of each rule)? If not, it writes a line to `~/.local/state/ai/misses.jsonl`.
7. **ai-doctor.** It reads the miss log and the gate log of the last 7 days. It also checks that each tool still has its contract and that the versions equal the pins. A rule that misses often needs a better regex, a clearer skill description, or an eval.

So: router nudges, skill fires, proof is logged, a miss is logged, `ai-doctor` reports it, and you fix the rule. See [docs/EXTENDING.md](EXTENDING.md) for how.

Known gaps: opencode has no hooks, so only the root rules apply there. Hermes has no per-prompt skill matching, so a small plugin does L2 and L3. Skills that only you can type (`grill-me`, `wait-what`, `retro`, `i-have-adhd`) cannot be forced: the agent suggests them.
