# Grounded Docs (arabold/docs-mcp-server)

Pin: `@arabold/docs-mcp-server` 3.4.1 (MIT). Intake done 2026-11-11 (SPEC section 21). Source: https://github.com/arabold/docs-mcp-server

## Vendor rules
Built-in server instructions (`src/mcp/defaultInstructions.ts` at v3.4.1, verbatim): "When a question depends on a library's API or behavior, search here before answering from memory." / "`search_docs` searches one library. Pass `version` when the project uses a specific version; without it, the newest indexed version is searched when there is one." / "Library names must match an indexed library. If a search cannot find the library, call `list_libraries` for the exact names and versions." / "This server is read-only and cannot index new documentation."
The repo ships Agent Skills in `skills/` and an AGENTS.md for repo development only. Do not import them. Read-only tools: `search_docs`, `read_page`, `list_pages`, `list_libraries`, `find_version`, `fetch_url`. Write tools: `scrape_docs`, `refresh_version`, `remove_docs`.

## When / when not
- Default for library docs (SPEC section 4), and the only source for pinned versions and private docs the owner indexed.
- Take the library name and version from `.ai/libs.md` (column `grounded-docs`, column `version`). Call `search_docs` with both. Skip `list_libraries` when the name is cached.
- `?` in the column means not indexed: go to context7. Do not scrape from a client.
- No `.ai/libs.md`: `list_libraries` once, then `search_docs`.
- Thin result: context7 next.
- Clients use the read-only tools. Scraping new docs is a server task, done by the owner or an admin session.
- Runs once on the home server. Other machines reach it over the private network (port 6280).

## Knowledge home, freshness, maintenance
- Home: `<repo>/.ai/libs.md`, column `grounded-docs` (written by `ai-libs --sync` from `list_libraries`).
- Fresh: same `lock:` line test as context7. A new index on the server shows up at the next `ai-libs --sync`.
- Maintain: `ai-libs --sync` prints the libraries that are not indexed. That list is the owner's to-do list for the docs server.

## Enforcement
- L0: AGENTS.md "Code navigation". L3: `docs-lookup` and `docs-on-dependency` rows (they show the cached name and version).
- Server flags: `--read-only` (or `DOCS_MCP_READ_ONLY=true`), `DOCS_MCP_TELEMETRY=false` (PostHog is on by default).

## Proof
- Should fire (EN): "how do I use the FastAPI dependency system?" First docs call is `search_docs` with `library` and `version` from `.ai/libs.md`.
- Should fire (RO): "cum folosesc sesiunile in sqlalchemy 2?"
- Should fire (RU): "как в pydantic v2 сделать валидатор поля?"
- Should not fire: "rename this variable".
- Signal: tool_use `mcp__plugin_ai-core_grounded-docs__search_docs`, a row in `~/.local/state/ai/docs-ids.jsonl`.

## Setup checklist
1. Server role in `install.sh`: `npm i -g --ignore-scripts @arabold/docs-mcp-server@3.4.1`, bind to the private network only, `ufw` allows 6280 from LAN and tailscale0 only.
2. Env: `DOCS_MCP_TELEMETRY=false` in the unit file.
3. Index libraries on the server (owner decides the list; start from the "not indexed" lines of `ai-libs --sync`). First scrape: UNVERIFIED size and time.
4. Clients: URL entry in the ai-core `.mcp.json` (`AI_DOCS_MCP_URL`, network transport), read-only. `ai-libs` uses the same URL.
5. Verify: `list_libraries` returns the indexed libraries from a client. `ss -ltn` on the server shows 6280 on the private addresses only.
6. Cleanup: remove the client entries, stop the unit, delete the data dir.
Intake done 2026-11-11: guarddog hits benign (provider-key presence checks; scraper file-type list used only when a GitHub repo is added as a source: index public library docs only). postinstall only echoes. Install with --ignore-scripts. Clients set DOCS_MCP_READ_ONLY=true. Telemetry off verified in code (DOCS_MCP_TELEMETRY=false).
