# Grounded Docs (arabold/docs-mcp-server)

Pin: `@arabold/docs-mcp-server` 3.4.1 (MIT). Intake done 2026-11-11 (SPEC section 21). Source: https://github.com/arabold/docs-mcp-server

## Vendor rules
No rule text published (contracts-mcp-b.md was not available). The repo ships Agent Skills in `skills/` and an AGENTS.md for repo development only. Do not import them. Read-only tools: `search_docs`, `read_page`, `list_pages`, `list_libraries`, `find_version`, `fetch_url`. Write tools: `scrape_docs`, `refresh_version`, `remove_docs`.

## When / when not
- Default for library docs (SPEC section 4). Step 1: `list_libraries`, then `search_docs` with library and project version.
- If the library is missing or the result is thin: context7.
- Clients use the read-only tools. Scraping new docs is a server task, done by the owner or an admin session.
- Runs once on the home server. Other machines reach it over the private network (port 6280).

## Enforcement
- L0: AGENTS.md "Code navigation". L3: `docs-lookup` and `docs-on-dependency` rows.
- Server flags: `--read-only` (or `DOCS_MCP_READ_ONLY=true`), `DOCS_MCP_TELEMETRY=false` (PostHog is on by default).

## Proof
- Should fire (EN): "how do I use the FastAPI dependency system?" First docs call is `search_docs`.
- Should fire (RU): "как в pydantic v2 сделать валидатор поля?"
- Should not fire: "rename this variable".
- Signal: tool_use `mcp__plugin_ai-core_grounded-docs__search_docs`.

## Setup checklist
1. Server role in `install.sh`: `npm i -g --ignore-scripts @arabold/docs-mcp-server@3.4.1`, bind to the private network only, `ufw` allows 6280 from LAN and tailscale0 only.
2. Env: `DOCS_MCP_TELEMETRY=false` in the unit file.
3. Index libraries on the server (owner decides the list). First scrape: UNVERIFIED size and time.
4. Clients: URL entry in the ai-core `.mcp.json` (network transport), read-only.
5. Verify: `list_libraries` returns the indexed libraries from a client. `ss -ltn` on the server shows 6280 on the private addresses only.
6. Cleanup: remove the client entries, stop the unit, delete the data dir.
Intake done 2026-11-11: guarddog hits benign (provider-key presence checks; scraper file-type list used only when a GitHub repo is added as a source: index public library docs only). postinstall only echoes. Install with --ignore-scripts. Clients set DOCS_MCP_READ_ONLY=true. Telemetry off verified in code (DOCS_MCP_TELEMETRY=false).
