# Serena

Pin: `serena-agent==2.1.0` (release v2.1.0). License GPL-3.0-or-later. Source: https://github.com/oraios/serena/tree/v2.1.0/src/serena/resources/config
Opt-in per project (owner decision 2026-11-12). Not loaded anywhere else.

## Vendor rules (verbatim, key lines of `contexts/claude-code.yml`)
- "You have access to Serena's code intelligence tools that exploit the symbolic structure of the code and are much more efficient than your own tools for most coding scenarios."
- "If you are working on any coding task and if Serena's tools are deferred, you should load them all immediately, before performing any read, grep or bash commands."
- "**CRITICAL**: Never use a tool before having read its schema via the tool-search tool!"
- "Especially when editing code you have read through Serena, **ALWAYS** use Serena's tools for editing, because your built-in tools will deny such edits (they will assume you haven't read the content)."
- Rule table: "Read -> FORBIDDEN for discovery. Use get_symbols_overview, then find_symbol with include_body. You may use read only if you already have an overview of the file and if reading whole symbols is inappropriate (e.g. a few lines of code)." / "Glob (by name) -> Allowed for discovery only." / "Grep (content) -> Allowed for discovery only; follow up reads or reference searches must be Serena." / "Edit -> FORBIDDEN. Use replace_symbol_body / insert_*_symbol / replace_content."
- System prompt: "CRITICAL: Before starting to work on a coding task, call the `initial_instructions` tool to read the 'Serena Instructions Manual'." and "Line numbers returned by Serena's tools are 0-based!"
- Codex context: "If Serena's tools can be used to achieve your task, you should prioritize them. In particular, it is important that you avoid reading entire source code files unless it is strictly necessary!"
- System prompt: "Maximizing parallel tool calls is the single biggest lever on cost".
The claude-code.yml quotes were read at main on 2026-11-10 (UNVERIFIED for 2.1.0 word for word). The memory quotes were read at the v2.1.0 tag on 2026-11-11.

## When / when not
- Turn it on for a project when symbol lookups pay off: a big repo (thousands of files), heavy refactors or renames across many files, a language where rg finds too many false hits. Small projects and box apps: leave it off; the Map plus rg is enough.
- On: `ai-adopt --tools serena`. It adds `serena` to `.ai/enabled`, sets `"enabledPlugins": {"ai-serena@ai": true}` in the project `.claude/settings.json` (the plugin `ai-serena@ai` holds only the Serena MCP entry; it is installed but off at user scope, and managed settings block project `.mcp.json` servers), writes `[mcp_servers.serena]` into `.codex/config.toml` (Codex loads it only in trusted projects), runs `serena project create --index`, and gitignores `.serena/cache/` and `.serena/project.local.yml`. Off: remove `serena` from `.ai/enabled`, the plugin key and the Codex entry.
- Gap: Hermes and opencode get no Serena.
- Where it is on: `initial_instructions` once, then `get_symbols_overview`, then `find_symbol` with `include_body`. Users: `find_referencing_symbols`. Edit with `replace_symbol_body`, `insert_before_symbol`, `insert_after_symbol`. Never built-in Edit on code you read with Serena. Lines start at 0. Batch independent calls.
- Memories are not used by default. Project knowledge lives in the repo AGENTS.md (Map and Libraries sections), which every agent reads with no tool call.
- Claude single-project mode (`--project-from-cwd`) has no `activate_project`. Do not call it.

## Knowledge home, freshness, maintenance
- Home: none of its own. The symbol index in `.serena/cache/` (gitignored) is rebuilt by Serena itself. `.serena/project.yml` is committed.
- Fresh: Serena updates the index during use. After a large pull: `serena project index`.

## Enforcement
- L1: opt-in routing row `serena` (session start line "Serena is on here") only in projects that enabled it.
- No nudges elsewhere. The old global `serena-first` row was removed (logs showed it ignored: 10 fired, 6 missed).
- Vendor `serena-hooks remind` is NOT used (issues #2251, #2204).
- L7: ai-doctor checks, only where enabled, that the project plugin key exists.

## Proof
- Should fire (EN, enabled project): "list the symbols in src/app/db.py". First call `get_symbols_overview`.
- Should fire (RO, enabled project): "arata-mi functia care calculeaza pretul in tracker.py". Expect `find_symbol`.
- Should fire (RU, enabled project): "где определён класс клиента и кто его вызывает?". Expect `find_symbol`, then `find_referencing_symbols`.
- Should not fire: any prompt in a project without `serena` in `.ai/enabled` (no Serena tools are loaded there); "edit the yaml config".
- Signal: tool_use `mcp__plugin_ai-serena_serena__*` in enabled projects only (UNVERIFIED exact prefix: check `/mcp`).

## Setup checklist
1. Install (per machine, by install.sh): `uv tool install -p 3.13 serena-agent==2.1.0`, and the plugin `ai-serena@ai` from our marketplace, off at user scope. Check `serena --version`. No global MCP registration, no Codex global `mcp add`.
2. `~/.serena/serena_config.yml`: `agent_interface: tools`, `excluded_tools: [execute_shell_command]`, `web_dashboard: false`, `language_backend: LSP`. Leave `trusted_project_path_patterns` empty.
3. Telemetry: `SERENA_USAGE_REPORTING=false` in the `ai-serena` plugin `.mcp.json` env and in the Codex project entry (ai-adopt writes it).
4. Per machine: `serena download-ls-dependencies <ls>` for the languages used.
5. Per project: `ai-adopt --tools serena`.
6. Verify: in an enabled project `/plugin` shows ai-serena enabled and `claude mcp list` shows serena; in other projects it does not. Nothing listens on port 24282.
7. Cleanup: remove the project plugin key and Codex entry, `claude plugin uninstall ai-serena@ai`, `uv tool uninstall serena-agent`, delete `~/.serena` and `<repo>/.serena/`.
