# Serena

Pin: `serena-agent==2.1.0` (release v2.1.0, not main 2.1.1.dev0). License GPL-3.0-or-later. Source: https://github.com/oraios/serena/tree/v2.1.0/src/serena/resources/config

## Vendor rules (verbatim, key lines of `contexts/claude-code.yml`)
- "You have access to Serena's code intelligence tools that exploit the symbolic structure of the code and are much more efficient than your own tools for most coding scenarios."
- "If you are working on any coding task and if Serena's tools are deferred, you should load them all immediately, before performing any read, grep or bash commands."
- "**CRITICAL**: Never use a tool before having read its schema via the tool-search tool!"
- "Especially when editing code you have read through Serena, **ALWAYS** use Serena's tools for editing, because your built-in tools will deny such edits (they will assume you haven't read the content)."
- Rule table: "Read -> FORBIDDEN for discovery. Use get_symbols_overview, then find_symbol with include_body. You may use read only if you already have an overview of the file and if reading whole symbols is inappropriate (e.g. a few lines of code)." / "Glob (by name) -> Allowed for discovery only." / "Grep (content) -> Allowed for discovery only; follow up reads or reference searches must be Serena." / "Edit -> FORBIDDEN. Use replace_symbol_body / insert_*_symbol / replace_content."
- System prompt: "CRITICAL: Before starting to work on a coding task, call the `initial_instructions` tool to read the 'Serena Instructions Manual'." and "Line numbers returned by Serena's tools are 0-based!"
- Codex context: "If Serena's tools can be used to achieve your task, you should prioritize them. In particular, it is important that you avoid reading entire source code files unless it is strictly necessary!"
- Memories (docs/02-usage/045_memories.md, src/serena/resources/memory_maintenance.md at v2.1.0): "Agents should read `mem:core` as the top-level entry point". "Prefer deliberate reads to triggers." "Dense agent notes, not prose docs." "Add or update memories only with stable, non-obvious project conventions". Onboarding "will read a lot of content ... switch to a new conversation once the onboarding is complete."
- System prompt: "Maximizing parallel tool calls is the single biggest lever on cost".
The claude-code.yml quotes were read at main on 2026-11-10 (UNVERIFIED for 2.1.0 word for word). The memory quotes were read at the v2.1.0 tag on 2026-11-11.

## When / when not
- Session start in a code repo: `initial_instructions` (it lists the memory names, or says onboarding is missing), then `read_memory core`. Read other memories only when core links to them for your task.
- Find code: graphify query first (see graphify.md), then `get_symbols_overview` on the located file, then `find_symbol` with `include_body`. Users of a symbol: `find_referencing_symbols`. Batch independent calls in one turn.
- Edit code: `replace_symbol_body`, `insert_before_symbol`, `insert_after_symbol`, `replace_content` for a few lines. Never built-in Edit on code you read with Serena.
- Built-in Read, Edit, Grep: non-code files only (md, json, yaml, toml, lock files). OMC lsp_* and ast-grep: fallback only.
- No .git: do not use Serena. If Serena fails, say so once, then use built-in tools.
- Claude in single-project mode (`--project-from-cwd`): `activate_project` does not exist. Do not call it. Codex: call `activate_project` with the repo path if `initial_instructions` says no project is active.

## Knowledge home, freshness, maintenance
- Home: `<repo>/.serena/memories/` (committed). Layout: `core` (entry point), `tech_stack`, `suggested_commands`, `conventions`, `task_completion`; `<module>/core` for big modules. Shared conventions: global memory `global/memory_maintenance` (from `ai/serena/memory_maintenance.md`, read-only).
- Sizes: core <= 60 lines, others <= 40 lines, all <= 16 KB.
- Fresh: the session start line says "memories stale" after 20 code commits or 5 added, deleted or renamed code files since the last memory commit. Stale or not, memories are hints: check a claim with a symbol lookup before an edit that depends on it.
- Maintain: after a commit that adds, deletes or renames modules, fix the source map in core (`edit_memory`). Add a memory only for a stable, non-obvious fact that took real work to find. Never one-off task notes, line numbers, secrets, tokens, hostnames, phone numbers, emails or other personal data: memories are pushed.
- Rename with `rename_memory` (it fixes `mem:` links). Check links: `serena memories check`.
- Project text always delivered: `.serena/project.yml` `initial_prompt` (ai-adopt sets it to point at core and `.ai/libs.md`).
- Onboarding: once per repo, in its own session (ai-adopt runs it headless). Never in the owner's working session. The headless run may use only Serena read, symbol-lookup and memory tools (`initial_instructions`, `onboarding`, `list_memories`, `read_memory`, `write_memory`, `list_dir`, `find_file`, `read_file`, `search_for_pattern`, `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `find_declaration`, `find_implementations`) and `graphify query|path|explain`: no edit tool, no shell.
- One home per fact: code facts in Serena memories. Session notes in the OMC notepad. Library IDs in `.ai/libs.md`. Do not copy AGENTS.md into memories.

## Enforcement
- L0: AGENTS.md "Code navigation".
- L1: routing rows `project-knowledge` (one status line: memory count, staleness, graph, docs map; never memory content) and `no-memories` (ask the owner to run ai-adopt). Vendor `serena-hooks activate` at SessionStart for Codex only (it names `activate_project`, which Claude single-project mode does not have); `cleanup` at SessionEnd.
- L3: context-only nudge `serena-first` on Read or Edit of code and Bash reads of code paths. 120 s quiet window. Never deny. Row `knowledge-check` after a git commit: update core when modules moved.
- Vendor `serena-hooks remind` is NOT used (issues #2251 blocks instead of reminding, #2204 false counts). Revisit when fixed.
- Claude: `alwaysLoad: true` on the server so tools are not deferred.
- L7: ai-doctor checks core and the four vendor memories exist, size caps, staleness, a secret scan over the memories, `initial_prompt`, the gitignore lines, and stale entries in `~/.serena/serena_config.yml`.

## Proof
- Should fire (EN): "list the symbols in src/app/db.py". First call `get_symbols_overview`.
- Should fire (RO): "arata-mi functia care calculeaza pretul in tracker.py". Expect `find_symbol`.
- Should fire (RU): "где определён класс клиента и кто его вызывает?". Expect graphify query, then `find_symbol`, then `find_referencing_symbols`.
- Session start in an adopted repo: the first two Serena calls are `initial_instructions` and `read_memory` of `core`, before any Read of a code file.
- Should not fire: "edit the yaml config". Built-in Edit is fine.
- Signal: Serena tool_use names (`mcp__plugin_ai-core_serena__*`) in the transcript. `misses.jsonl` has no `project-knowledge` row for the session.

## Setup checklist
1. Install: `uv tool install -p 3.13 serena-agent==2.1.0`. Check `serena --version`.
2. `serena init`. Then set in `~/.serena/serena_config.yml`: `agent_interface: tools`, `excluded_tools: [execute_shell_command, serena_repl]` (serena_repl may be a no-op: check `serena tools list`), `web_dashboard: false`, `language_backend: LSP`, `read_only_memory_patterns: ["global/.*"]`. Leave `trusted_project_path_patterns` empty.
3. Global conventions: copy `ai/serena/memory_maintenance.md` to `~/.serena/memories/global/memory_maintenance.md` (install.sh; ai-adopt does it too when missing). Serena then uses it and does not seed a project copy.
4. Telemetry: `SERENA_USAGE_REPORTING=false` in each MCP server entry `env` (the client starts the server, a shell export is not enough).
5. Register: through the ai-core plugin `.mcp.json` (server `serena`, args `start-mcp-server --project-from-cwd --context=claude-code`). Codex: `codex mcp add` with `--context=codex`. Hermes by hand with `--context ide`. Remove any hand-made user-scope registration (no duplicates). Do not run `serena setup` where the plugin does it.
6. Per machine: `serena download-ls-dependencies <ls>` for the languages used.
7. Per project: `ai-adopt`. It runs `serena project create --index` (or `serena project index`), sets `initial_prompt`, runs onboarding headless when no memories exist, adds `.serena/cache/` and `.serena/project.local.yml` to `.gitignore`, and commits `.serena/project.yml`, `.serena/.gitignore` and `.serena/memories/` after the owner reads the diff.
8. Verify: `serena --version`, `serena tools list`, `claude mcp list`, `codex mcp list`, `serena memories check` in an adopted repo. Nothing listens on port 24282.
9. Cleanup: remove the MCP entries and hook entries, `uv tool uninstall serena-agent`, delete `~/.serena` (back up `memories/global/`), delete `<repo>/.serena/` after checking memories.
Open: does `--project-from-cwd` auto-create `.serena/project.yml` in a bare git repo (test).
