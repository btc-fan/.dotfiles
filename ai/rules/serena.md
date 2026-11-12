# Serena

Pin: `serena-agent==2.1.0` (release v2.1.0). License GPL-3.0-or-later. Source: https://github.com/oraios/serena/tree/v2.1.0/src/serena/resources/config
On by default in every project (owner decision 2026-11-12 evening). A project opts out with a line `no-serena` in `.ai/enabled`.

## Vendor rules (verbatim, key lines of `contexts/claude-code.yml`)
- "You have access to Serena's code intelligence tools that exploit the symbolic structure of the code and are much more efficient than your own tools for most coding scenarios."
- "If you are working on any coding task and if Serena's tools are deferred, you should load them all immediately, before performing any read, grep or bash commands."
- "**CRITICAL**: Never use a tool before having read its schema via the tool-search tool!"
- "Especially when editing code you have read through Serena, **ALWAYS** use Serena's tools for editing, because your built-in tools will deny such edits (they will assume you haven't read the content)."
- Rule table: "Read -> FORBIDDEN for discovery. Use get_symbols_overview, then find_symbol with include_body. You may use read only if you already have an overview of the file and if reading whole symbols is inappropriate (e.g. a few lines of code)." / "Glob (by name) -> Allowed for discovery only." / "Grep (content) -> Allowed for discovery only; follow up reads or reference searches must be Serena." / "Edit -> FORBIDDEN. Use replace_symbol_body / insert_*_symbol / replace_content."
- System prompt: "Line numbers returned by Serena's tools are 0-based!"
- Codex context: "If Serena's tools can be used to achieve your task, you should prioritize them. In particular, it is important that you avoid reading entire source code files unless it is strictly necessary!"
- System prompt: "Maximizing parallel tool calls is the single biggest lever on cost".
The claude-code.yml quotes were read at main on 2026-11-10 (UNVERIFIED for 2.1.0 word for word).

## When / when not
- Navigation order in every repo: the AGENTS.md Map, then `graphify query` (structure), then Serena symbol tools (definitions, references, edits), then a narrow `rg` and reading only the located lines.
- Serena tools: `get_symbols_overview`, then `find_symbol` with `include_body`. Users: `find_referencing_symbols`. Edit with `replace_symbol_body`, `insert_before_symbol`, `insert_after_symbol`. Never built-in Edit on code you read with Serena. Lines start at 0. Batch independent calls.
- Mode `no-memories`: no memories and no onboarding. The AGENTS.md Map is the one knowledge place. Do not call memory or onboarding tools.
- Answers are cut at 40k characters: ask for one symbol or one file at a time.
- Opt out for one project: add `no-serena` to `.ai/enabled` (a repo where the language server is too slow or wrong).
- `--project-from-cwd` single-project mode has no `activate_project`. Do not call it.

## Knowledge home, freshness, maintenance
- Home: none of its own (no memories). The symbol index in `.serena/cache/` (gitignored) is rebuilt by Serena itself. `.serena/project.yml` is committed.
- Fresh: Serena updates the index during use. After a large pull: `serena project index`.

## Enforcement
- L1: routing row `serena` (session start line "Serena is on here") in every code repo without `no-serena`.
- Not used: vendor `serena-hooks remind` (issues #2251, #2204), the claude-code system-prompt override, the web dashboard.
- L7: ai-doctor checks the global registrations and, per project, the opt-out line.

## Proof
- Should fire (EN): "list the symbols in src/app/db.py". First call `get_symbols_overview`.
- Should fire (RO): "arata-mi functia care calculeaza pretul in tracker.py". Expect `find_symbol`.
- Should fire (RU): "где определён класс клиента и кто его вызывает?". Expect `find_symbol`, then `find_referencing_symbols`.
- Should not fire: the same prompts in a project with `no-serena` in `.ai/enabled`; "edit the yaml config".
- Signal: tool_use of the Serena MCP tools (Claude: the `ai-serena` plugin server; check the exact prefix in `/mcp`).

## Setup checklist
1. Install (per machine, by install.sh): `uv tool install -p 3.13 serena-agent==2.1.0`. Global registration: Claude through the plugin `ai-serena@ai`, on at user scope (`--context=claude-code`); Codex `codex mcp add` (`--context=codex`); Hermes `hermes mcp add` (`--context=ide`). All with `--project-from-cwd` and mode `no-memories`.
2. `~/.serena/serena_config.yml`: `agent_interface: tools`, `excluded_tools: [execute_shell_command]`, `web_dashboard: false`, `language_backend: LSP`, answer limit 40k characters. Leave `trusted_project_path_patterns` empty.
3. Telemetry: `SERENA_USAGE_REPORTING=false` in each server entry `env`.
4. Per machine: `serena download-ls-dependencies <ls>` for the languages used.
5. Per project: `ai-adopt` runs `serena project create --index` (unless `no-serena`) and gitignores `.serena/cache/` and `.serena/project.local.yml`.
6. Verify: `claude mcp list`, `codex mcp list` and `hermes mcp list` show serena. Nothing listens on port 24282.
7. Cleanup: `claude plugin uninstall ai-serena@ai`, remove the Codex and Hermes entries, `uv tool uninstall serena-agent`, delete `~/.serena` and `<repo>/.serena/`.
