
Code navigation
- Order in a repo: the Map and Libraries sections of its AGENTS.md first. Then:
  1. Wide question (where, how, what breaks): graphify query "<question>" --budget 1500, or graphify affected "<path>::<symbol>".
  2. Exact symbol, its callers, an edit: Serena find_symbol, find_referencing_symbols, replace_symbol_body.
  3. Text only (strings, config, logs): a narrow rg, then read only the located lines. Do not scan whole folders.
- Serena and graphify are on in every project unless .ai/enabled says no-serena or no-graph (the session start line says so). Serena down: say so, use graphify and rg, and tell the owner. The owner can ask you to fix or switch it off (add no-serena to .ai/enabled).
- Knowledge lives in the repo only: the Map, GLOSSARY.md, docs/adr, docs/research. No Serena memories, no Claude auto memory.
- After a commit that adds, deletes or renames modules, update the Map section. After a dependency change, run ai-libs --sync. Never put secrets or personal data in AGENTS.md.
- Library, SDK, API or CLI code: look up docs before you write it. Use context7 query-docs with the ID from the Libraries section (resolve-library-id only when there is no ID). If context7 has nothing: the official docs site, then the library source, and say so. No general web search for docs (Codex too). No secrets or private code in a docs query.
- GitHub: the gh CLI, read-only (view, list, diff, checks) unless I ask for a change. Exception: the git workflow below (push the feature branch, draft PR, gh pr ready, gh pr merge after the owner's OK). A PR follows the pull request rules below.
