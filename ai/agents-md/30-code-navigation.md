
Code navigation
Order: graphify first, then Serena, then read only the lines they located.
- Question about a codebase ("where is X", "what calls Y"): run graphify query before your first grep or file read.
- No graphify-out/graph.json: run graphify . first (free, local, code only).
- Read or edit code: use Serena. get_symbols_overview, then find_symbol with include_body. Edit with replace_symbol_body or insert_before_symbol, insert_after_symbol. Do not use built-in Edit on code you read with Serena.
- Who uses a symbol: find_referencing_symbols.
- Built-in Read, Edit and Grep are fine for non-code files (md, json, yaml, toml, env, lock files).
- OMC lsp_* and ast-grep tools: fallback only.
- Serena line numbers start at 0. No .git and no .serena in the project: do not use Serena. If Serena fails, say so once, then use built-in tools.
- After you change code, run graphify update . (AST only, no cost).
- Library, framework, SDK, API or CLI question: look up docs before you write code. Step 1 Grounded Docs. Step 2 context7. Step 3 library source or official site, and say that docs were not found. Use the project version. Send no secrets and no private code in a docs query.
Details: ~/.config/ai/rules/graphify.md, serena.md, grounded-docs.md, context7.md.
