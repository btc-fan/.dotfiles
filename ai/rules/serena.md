# Serena

Pin: `serena-agent==2.1.0` (release v2.1.0, not main 2.1.1.dev0). License GPL-3.0-or-later. Source: https://github.com/oraios/serena/tree/main/src/serena/resources/config

## Vendor rules (verbatim, key lines of `contexts/claude-code.yml`)
- "You have access to Serena's code intelligence tools that exploit the symbolic structure of the code and are much more efficient than your own tools for most coding scenarios."
- "If you are working on any coding task and if Serena's tools are deferred, you should load them all immediately, before performing any read, grep or bash commands."
- "**CRITICAL**: Never use a tool before having read its schema via the tool-search tool!"
- "Especially when editing code you have read through Serena, **ALWAYS** use Serena's tools for editing, because your built-in tools will deny such edits (they will assume you haven't read the content)."
- Rule table: "Read -> FORBIDDEN for discovery. Use get_symbols_overview, then find_symbol with include_body. You may use read only if you already have an overview of the file and if reading whole symbols is inappropriate (e.g. a few lines of code)." / "Glob (by name) -> Allowed for discovery only." / "Grep (content) -> Allowed for discovery only; follow up reads or reference searches must be Serena." / "Edit -> FORBIDDEN. Use replace_symbol_body / insert_*_symbol / replace_content."
- System prompt: "CRITICAL: Before starting to work on a coding task, call the `initial_instructions` tool to read the 'Serena Instructions Manual'." and "Line numbers returned by Serena's tools are 0-based!"
- Codex context: "If Serena's tools can be used to achieve your task, you should prioritize them. In particular, it is important that you avoid reading entire source code files unless it is strictly necessary!"
Full files at the pin: not copied here (UNVERIFIED that the quotes match 2.1.0 exactly; they were read at main on 2026-11-10).

## When / when not
- In a code project use Serena first to read and edit code. Load its tools before any read, grep or bash on code.
- Read: get_symbols_overview, then find_symbol with include_body. Whole file only if it is a few lines or Serena failed.
- Users of a symbol: find_referencing_symbols. Edit: replace_symbol_body, insert_before_symbol, insert_after_symbol, replace_content for a few lines.
- graphify owns discovery. Serena owns reading and editing code. Built-in Read, Edit, Grep are fine for non-code files.
- OMC lsp_* and ast-grep: fallback only.
- No .git and no .serena: do not use Serena. If it fails, say so once, then use built-in tools.
- `.serena/`: commit project.yml and memories. Gitignore cache/, project.local.yml, logs/.
- Code facts go to Serena memories. Session notes go to OMC notepad.

## Enforcement
- L0: AGENTS.md "Code navigation". L1: vendor `serena-hooks activate` at SessionStart (Claude, Codex), `cleanup` at SessionEnd.
- L3: our own context-only nudge `serena-first` on Read or Edit of code and Bash reads of code paths. 120 s quiet window. Never deny.
- Vendor `serena-hooks remind` is NOT used (issues #2251 blocks instead of reminding, #2204 false counts). Revisit when fixed.
- Claude: `alwaysLoad: true` on the server so tools are not deferred.
- L7: ai-doctor reports stale entries in `~/.serena/serena_config.yml` (no unregister command exists).

## Proof
- Should fire (EN): "list the symbols in src/md999/db.py". First call `get_symbols_overview`.
- Should fire (RO): "arata-mi functia care calculeaza pretul in tracker.py". Expect `find_symbol`.
- Should not fire: "edit the yaml config". Built-in Edit is fine.
- Signal: Serena tool_use names (`mcp__plugin_ai-core_serena__*`) in the transcript.

## Setup checklist
1. Install: `uv tool install -p 3.13 serena-agent==2.1.0`. Check `serena --version`.
2. `serena init`. Then set in `~/.serena/serena_config.yml`: `agent_interface: tools`, `excluded_tools: [execute_shell_command, serena_repl]` (serena_repl may be a no-op: check `serena tools list`), `web_dashboard: false`, `language_backend: LSP`. Leave `trusted_project_path_patterns` empty.
3. Telemetry: `SERENA_USAGE_REPORTING=false` in each MCP server entry `env` (the client starts the server, a shell export is not enough).
4. Register: through the ai-core plugin `.mcp.json` (server `serena`, args `start-mcp-server --project-from-cwd --context=claude-code`). Codex: `codex mcp add` with `--context=codex`. Hermes by hand with `--context ide`. Remove any hand-made user-scope registration (no duplicates). Do not run `serena setup` where the plugin does it.
5. Per machine: `serena download-ls-dependencies <ls>` for the languages used.
6. Per project: `serena project create --index` (or first start). Add the three gitignore lines. `serena project health-check`.
7. Verify: `serena --version`, `serena tools list`, `claude mcp list`, `codex mcp list`. Nothing listens on port 24282.
8. Cleanup: remove the MCP entries and hook entries, `uv tool uninstall serena-agent`, delete `~/.serena` (back up `memories/global/`), delete `<repo>/.serena/` after checking memories.
Open: does `--project-from-cwd` auto-create `.serena/project.yml` in a bare git repo (test).
