# context7

Pin: `@upstash/context7-mcp@4.6.0` (never @latest). Source: https://github.com/upstash/context7

## Vendor rules (verbatim)
- Root README: "Always use Context7 when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask."
- `rules/context7-mcp.md`: "Use Context7 MCP to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service ... Use even when you think you know the answer ... Prefer this over web search for library docs."
- Same file: "Do not use for: refactoring, debugging, or reviewing code that does not depend on a library or platform API, or general programming concepts."
- Steps: "Always start with `resolve-library-id` ... unless the user provides an exact library ID in `/org/project` format"; pick by name match, relevance, snippet count, reputation, benchmark score; then `query-docs` "scoped to a single concept"; one call per concept.
Quotes read at the repo head on 2026-11-10, not at the 4.6.0 tag: UNVERIFIED for the tag.

## When / when not
- Fallback after Grounded Docs. Order: Grounded Docs, then context7, then library source or official site.
- Use the project version. One concept per call.
- Queries leave the machine (query, library id, key, client name, IP). No secrets and no private code in a query.
- Free plan: 1,000 calls per month.

## Enforcement
- L0: AGENTS.md "Code navigation" and the `docs-lookup` row. L3: `docs-lookup` prompt row and `docs-on-dependency` nudge (once per library per session).
- PostToolUse on the docs tools records looked-up libraries.
- L4: none. Nudges only.

## Proof
- Should fire (EN): "use context7 to show the Next.js app router setup". `resolve-library-id` then `query-docs`.
- Should fire (RO): "cum configurez Tailwind v4 in Vite? verifica documentatia".
- Should not fire: "refactor this function to be shorter".
- Signal: tool_use `mcp__plugin_ai-core_context7__resolve-library-id` then `query-docs`.

## Setup checklist
1. Pin: `npx -y @upstash/context7-mcp@4.6.0` (Node pinned by the installer). Run once to warm the npm cache.
2. Key: the free key is hardcoded in `ai/marketplace/plugins/ai-core/.mcp.json` `env` (owner exception, SPEC 13). Never as `--api-key` (visible in the process list). Worst case is quota abuse: rotate in one place.
3. Do NOT run `npx ctx7 setup` (duplicates MCP config, rules and a skill). Do not use the Claude context7 plugin (dropped, duplicate).
4. Codex: `codex mcp add` with `env`. Test that the key reaches the process (`env_vars` semantics UNVERIFIED). Hermes: `hermes mcp add`.
5. Verify: `claude mcp list` and `/mcp` show it connected. Tool list: `npx -y @modelcontextprotocol/inspector npx @upstash/context7-mcp@4.6.0` shows `resolve-library-id` and `query-docs`. The CLI works without a key, so it proves the network, not the key: check the call count on the dashboard.
6. Cleanup: remove the MCP entries. If `ctx7 setup` ever ran: `npx ctx7 remove`. Revoke the key in the dashboard.
