
Code navigation
- In a repo, read the Map and Libraries sections of its AGENTS.md first. Then search narrowly (rg, Grep, Glob) and read only the lines you located. Do not scan whole folders.
- Serena or graphify only where the project turned them on (the session start line says so).
- After a commit that adds, deletes or renames modules, update the Map section. After a dependency change, run ai-libs --sync. Never put secrets or personal data in AGENTS.md.
- Library, SDK, API or CLI code: look up docs before you write it. Use context7 query-docs with the ID from the Libraries section (resolve-library-id only when there is no ID). If context7 has nothing: the official docs site, then the library source, and say so. No general web search for docs (Codex too). No secrets or private code in a docs query.
- GitHub: the gh CLI, read-only (view, list, diff, checks) unless I ask for a change. A PR follows the pull request rules below.
