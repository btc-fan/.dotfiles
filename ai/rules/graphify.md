# graphify

Pin: PyPI `graphifyy` 0.9.105. Source: https://github.com/Graphify-Labs/graphify
On by default in every project (owner decision 2026-11-12 evening). A project opts out with a line `no-graph` in `.ai/enabled`. CLI only, no MCP server.

## Vendor rules (verbatim, AGENTS.md variant)
The verbatim block is the file `ai/rules/vendor/graphify-0.9.105-always-on-agents-md.md` (byte copy from the audited intake copy).
Deviation rule: delete the `/graphify` line on an agent where the graphify skill is not installed. Whether the intake copy equals 0.9.105: UNVERIFIED.
README at v0.9.105 (verbatim): "A code-only corpus requires no API key: `graphify extract` runs fully offline. On a mixed repo, add `--code-only` to index just the code and skip the docs/PDFs/images that would otherwise need an LLM." / "set `GRAPHIFY_BACKEND=none` to disable all LLM backends (semantic extraction and the `claude -p` labeling fallback) and keep a code-only graph." / "`graphify hook install`: auto-rebuild on commit + branch checkout (run `graphify update .` after `git pull`)".

## When / when not
- Navigation order in every repo: the AGENTS.md Map, then `graphify query` (structure), then Serena symbol tools, then a narrow `rg` and reading only the located lines.
- Commands: `graphify query "<question>"`, `graphify path "<A>" "<B>"`, `graphify explain "<concept>"`.
- Opt out for one project: add `no-graph` to `.ai/enabled`.
- Never bare `graphify .` (the skill form; headless it asks for an LLM key and fails). No semantic pass, no Graphify Cloud, no `ingest`. Never `graphify claude install` or `graphify agents install` in a project.

## Knowledge home, freshness, maintenance
- Home: `<repo>/graphify-out/` (generated, gitignored).
- Build: `ai-adopt` runs `GRAPHIFY_BACKEND=none graphify extract . --code-only` (local, no key, nothing leaves the machine) and `graphify hook install` (git hooks rebuild the graph after commit, checkout, merge and rebase).
- Agent git calls run no git hooks on a server (the git guard), so the router refreshes the graph itself: after a successful git commit, merge, pull, checkout, switch or rebase (Claude and Codex) it starts `graphify update <repo>` in the background (keyless, code only). Agents do not run it by hand.
- Fresh: `graph.json` newer than the last code commit; the session start line says "graph stale" otherwise.

## Enforcement
- L1: routing row `graph` (session start line) in every code repo without `no-graph`. The router refreshes the graph after agent git calls; `knowledge-check` no longer asks for `graphify update .` when that refresh was started.
- Advisory only. Never `--strict`. `GRAPHIFY_HOOK_STRICT=0`.
- L7: `~/.cache/graphify-queries.log`.

## Proof
- Should fire (EN): "where is the price drop alert computed?". First exploring call is `graphify query`.
- Should fire (RO): "unde se calculeaza istoricul de pret in proiectul asta?"
- Should fire (RU): "где считается история цен в этом проекте?"
- Should not fire: the same prompts in a project with `no-graph` in `.ai/enabled` (expect the Map, Serena, then rg).
- Signal: a new line in `~/.cache/graphify-queries.log`.

## Setup checklist
1. Install (per machine): `uv tool install graphifyy==0.9.105`.
2. Env (agent env and `~/.config/ai/env`): `GRAPHIFY_BACKEND=none`, `GRAPHIFY_HOOK_STRICT=0`. The build command also sets `GRAPHIFY_BACKEND=none` inline.
3. No optional extras (`mcp`, `watch`, `video`, cloud). Telemetry: none documented.
4. Per project: `ai-adopt` (build + git hooks), unless `no-graph`.
5. Verify: `graphify --version` prints 0.9.105. In a project with no LLM key set, `GRAPHIFY_BACKEND=none graphify extract . --code-only` prints a node count; `graphify hook status` shows the hooks.
6. Cleanup: `graphify hook uninstall` per repo, `uv tool uninstall graphifyy`, delete `graphify-out/` and the query log.
