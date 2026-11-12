# context7

Pin: `@upstash/context7-mcp@4.6.0` (never @latest). Source: https://github.com/upstash/context7

## Vendor rules (verbatim)
- Root README: "Always use Context7 when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask."
- `rules/context7-mcp.md`: "Use Context7 MCP to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service ... Use even when you think you know the answer ... Prefer this over web search for library docs."
- Same file: "Do not use for: refactoring, debugging, or reviewing code that does not depend on a library or platform API, or general programming concepts."
- Steps: "Always start with `resolve-library-id` ... unless the user provides an exact library ID in `/org/project` format"; pick by name match, relevance, snippet count, reputation, benchmark score; then `query-docs` "scoped to a single concept"; one call per concept.
- `docs/tips.mdx`: "If you already know exactly which library you want ... skip the library-matching step". Tool text: "Do not call this tool more than 3 times per question." and "If you know the programming language the user is working in, pass it as `language`".
Quotes read at the repo head on 2026-11-10 and 2026-11-11, not at the 4.6.0 tag: UNVERIFIED for the tag.

## When / when not
- Any code that calls a library, framework, SDK, CLI or cloud API: look up docs before you write it. This includes prompts that only name the library ("write httpx code with retries"). Prefer docs MCPs over web search. Codex: use this MCP, not `web_search`, for library docs.
- Order: `.ai/libs.md` first, Grounded Docs second (see grounded-docs.md), context7 third, then the library source or official site (say that docs were not found).
- `.ai/libs.md` has a context7 ID for the library: call `query-docs` with that ID directly. Do not call `resolve-library-id`. A versioned ID (`/org/project/vX`) wins when listed.
- No ID: call `resolve-library-id` once, then `query-docs`. Run `ai-libs --sync` before your next commit so the ID is cached.
- One concept per call. Pass `language`. At most 3 calls per question.
- Queries leave the machine (query, library id, key, client name, IP). No secrets and no private code in a query.
- Free plan: 1,000 calls per month. Cached IDs save about half.

## Knowledge home, freshness, maintenance
- Home: `<repo>/.ai/libs.md`, column `context7` (committed, written by `ai-libs --sync`).
- Fresh: its `lock:` line hash equals the lockfile hash. The session start line says "docs map stale" when not.
- Maintain: after a manifest or lockfile change, or after you resolved a new ID, run `ai-libs --sync` and commit `.ai/libs.md`.
- What `ai-libs` sends (owner approved 2026-11-12): only public library names, one search call per library, once (the ID is then cached in `.ai/libs.md`). Never code. Never local, path, git or workspace packages. If any non-public index is configured anywhere for an ecosystem (lockfile sources and tarball URLs, `.npmrc` `registry=` or `@scope:registry=`, `.yarnrc`, pip.conf, `PIP_*`/`UV_*` env, `[tool.uv]` index, `[[tool.poetry.source]]`, `uv.toml`, `.cargo/config.toml` registries, `GOPRIVATE`/`GONOPROXY`/`GONOSUMDB`/`GOPROXY` also from `go env`), no name of that ecosystem is sent and the output says so. Public means an exact hostname on an allow list. Such rows get the note `local package` or `private registry` and `-`. `ai-libs --check` is read-only and refuses `--sync`. The router logs every ID you used to `~/.local/state/ai/docs-ids.jsonl`; `ai-libs` reads that log before it calls the API.

## Enforcement
- L0: AGENTS.md "Code navigation" and the `docs-lookup` row.
- L3: `docs-lookup` prompt row (also fires when the prompt names a library from `.ai/libs.md`, and shows the cached IDs) and `docs-on-dependency` nudge (once per library per session).
- PostToolUse on the docs tools records looked-up libraries and IDs. Row `knowledge-check` after a commit asks for `ai-libs --sync` when a new ID was used.
- L4: none. Nudges only.

## Proof
- Should fire (EN): "use context7 to show the Next.js app router setup". `resolve-library-id` then `query-docs`.
- Should fire (EN, adopted repo with httpx in `.ai/libs.md`): "write httpx code with retries". First docs call is `query-docs` with the cached ID, no `resolve-library-id`.
- Should fire (RO): "cum configurez Tailwind v4 in Vite? verifica documentatia".
- Should fire (RU): "как настроить ретраи в httpx?"
- Should not fire: "refactor this function to be shorter".
- Signal: tool_use `mcp__plugin_ai-core_context7__query-docs`, a row in `docs-ids.jsonl`.

## Setup checklist
1. Pin: install.sh installs `@upstash/context7-mcp@4.6.0` once under `~/.local/share/ai/npm/` (integrity checked, audited, `--ignore-scripts`). The plugin runs it through `mcp/context7.sh`. No npx at runtime.
2. Key: `CONTEXT7_API_KEY` from the environment or `~/.config/ai/secrets.env`, else the free key in `mcp/context7.sh` (owner exception, SPEC 13). Never as `--api-key` (visible in the process list). Worst case is quota abuse: rotate in one place. `ai-libs` uses the same key order for its HTTP lookups (`https://context7.com/api/v2/libs/search`).
3. Do NOT run `npx ctx7 setup` (duplicates MCP config, rules and a skill). Do not use the Claude context7 plugin (dropped, duplicate).
4. Codex: `codex mcp add` with `env`. Test that the key reaches the process (`env_vars` semantics UNVERIFIED). Hermes: `hermes mcp add`.
5. Per project: `ai-libs --sync` (ai-adopt runs it).
6. Verify: `claude mcp list` and `/mcp` show it connected. In an adopted repo, `ai-libs --check` exits 0. The CLI works without a key, so it proves the network, not the key: check the call count on the dashboard.
7. Cleanup: remove the MCP entries. If `ctx7 setup` ever ran: `npx ctx7 remove`. Revoke the key in the dashboard.
