
Code navigation
Goal: never explore a repo from zero. Read the stored knowledge first, then only the lines you need.
- Session start in a code repo: call Serena initial_instructions, then read_memory core. Read other memories only through links in core. Memories are hints, the code wins: check a claim with a Serena lookup before an edit that depends on it. No memories: tell me to run ai-adopt.
- Codebase question ("where is X", "what calls Y"): graphify query first, before any grep or file read. No graphify-out/graph.json: GRAPHIFY_BACKEND=none graphify extract . --code-only (free, local, no key). Never bare graphify .
- Read code: get_symbols_overview on the located file, then find_symbol with include_body. Users: find_referencing_symbols. Edit: replace_symbol_body, insert_before_symbol, insert_after_symbol. Never built-in Edit on code you read with Serena. Batch independent calls in one turn.
- Built-in Read, Edit, Grep: non-code files only (md, json, yaml, toml, env, lock). OMC lsp_* and ast-grep: fallback only. Serena lines start at 0. No .git: no Serena. If Serena fails, say so once, then use built-in tools.
- After code changes: graphify update . After a commit that adds, deletes or renames modules: fix the source map in mem:core (edit_memory).
- Library code (any library, framework, SDK, API or CLI, even when only its name is in the task): look up docs before you write code. First .ai/libs.md: it has the version and the IDs. Then Grounded Docs search_docs with that name and version. Then context7 query-docs with the cached ID (resolve-library-id only when no ID is cached). Then the source or official site, and say docs were not found. Docs MCPs before web search (Codex: context7 query-docs, not web_search). No secrets or private code in queries. New ID or changed lockfile: ai-libs --sync before the commit.
- One home per fact: code facts in Serena memories, library IDs in .ai/libs.md, session notes in the OMC notepad. Never secrets or personal data in memories (they are pushed). Do not copy this file into memories.
Details: ~/.config/ai/rules/graphify.md, serena.md, grounded-docs.md, context7.md.
