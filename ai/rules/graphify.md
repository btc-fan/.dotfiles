# graphify

Pin: PyPI `graphifyy` 0.9.105. Source: https://github.com/Graphify-Labs/graphify, https://docs.graphify.com/guides/always-on

## Vendor rules (verbatim, AGENTS.md variant)
The verbatim block is the file `ai/rules/vendor/graphify-0.9.105-always-on-agents-md.md` (byte copy from the audited intake copy).
Deviation rule: delete the `/graphify` line on an agent where the graphify skill is not installed. Whether the intake copy equals 0.9.105: UNVERIFIED.
README at v0.9.105 (verbatim): "A code-only corpus requires no API key: `graphify extract` runs fully offline. On a mixed repo, add `--code-only` to index just the code and skip the docs/PDFs/images that would otherwise need an LLM." / "set `GRAPHIFY_BACKEND=none` to disable all LLM backends (semantic extraction and the `claude -p` labeling fallback) and keep a code-only graph." / "`graphify hook install`: auto-rebuild on commit + branch checkout (run `graphify update .` after `git pull`)".

## When / when not
- Use in any git repo with code: "where is X", "what calls Y", "how do A and B connect". Query: `graphify query "<question>"`, `graphify path "<A>" "<B>"`, `graphify explain "<concept>"`. Then Serena for the exact symbol. Then read only the located lines.
- Build (one form everywhere, no key, nothing leaves the machine): `GRAPHIFY_BACKEND=none graphify extract . --code-only`. Never bare `graphify .` (it is the `/graphify` skill form; headless it asks for an LLM key and fails).
- Update after code changes: `graphify update .` (AST only, no cost).
- graphify owns discovery. Serena owns reading and editing symbols. Built-in Read and Edit are for non-code files.
- Do not use without `graphify-out/graph.json` (build first), for non-code repos, or when the owner says not to.
- No semantic pass on docs, PDFs, images or video. It needs an LLM. Ask the owner first.
- No Graphify Cloud. No `ingest`.
- Never run `graphify claude install` or `graphify agents install` in a project. The global rule replaces them.

## Knowledge home, freshness, maintenance
- Home: `<repo>/graphify-out/` (generated, gitignored by ai-adopt).
- Fresh: `graph.json` is newer than the last commit that touched code. The session start line says "graph stale" when not.
- Maintain: `graphify update .` after you change code and after `git pull`. No git hook by default (owner decision 2026-11-12: the router's post-commit nudge covers freshness). Optional owner step for one project: `graphify hook install` in the repo (rebuilds detached on commit and branch checkout; remove with `graphify hook uninstall`). On a big repo the checkout rebuild can be heavy.

## Enforcement
- L0: AGENTS.md "Code navigation" and vendor short form.
- L1: the `project-knowledge` status line at session start (graph fresh, stale or missing); the routing table after compaction or /clear. Vendor `compact` hook resets the nudge budget.
- L3: routing rows `no-graph`, `graph-first` (log only), `graph-update`, `knowledge-check` (after a commit, when no graphify git hook is installed).
- L4: none. Advisory only. Never `--strict`. Set `GRAPHIFY_HOOK_STRICT=0`.
- L5: the rule goes into SubagentStart context and into "Prompting other agents".
- L7: `~/.cache/graphify-queries.log` (JSONL). Keep it on.
- Non-Claude agents get L0 only.

## Proof
- Should fire (EN): "where is the price drop alert computed?" in a repo with a graph. First exploring call is `graphify query`.
- Should fire (RO): "unde se calculeaza istoricul de pret in proiectul asta?"
- Should fire (RU): "где считается история цен в этом проекте?"
- Should not fire: "rewrite the intro of README.md". A repo without a graph gets the build nudge, not a query.
- Signal: new line in `~/.cache/graphify-queries.log` and a Bash `graphify query` call before any Grep or Read.
- Eval bar: 3 of 3 fire, 0 of 2 false fire. See `ai/evals/tools.md`.

## Setup checklist
1. Install: `uv tool install graphifyy==0.9.105`. If not on PATH: `uv tool update-shell`. uv installer is curl-to-shell: audit it first.
2. Env (agent env and `~/.config/ai/env`): `GRAPHIFY_BACKEND=none`, `GRAPHIFY_HOOK_STRICT=0`. Reason: `graphify extract` picks any API key in the environment and would send code out. The build command also sets `GRAPHIFY_BACKEND=none` inline, so it is keyless even where the env is missing.
3. No optional extras (`mcp`, `watch`, `video`, cloud).
4. Per agent: `graphify install --platform codex|opencode|hermes|agents`. Test in a throwaway HOME and diff first. Never `graphify uninstall --purge`.
5. Telemetry: none documented. Auto-update check: UNVERIFIED.
6. Per project: `ai-adopt` runs `GRAPHIFY_BACKEND=none graphify extract . --code-only` and adds `graphify-out/` to `.gitignore`. No git hook (owner decision); optional owner step: `graphify hook install`.
7. Verify: `graphify --version` prints 0.9.105. `GRAPHIFY_BACKEND=none graphify extract . --code-only` in a repo with no key set prints a node count and writes `graphify-out/graph.json`. `graphify query "main entry point"` returns a subgraph. `tail -1 ~/.cache/graphify-queries.log`.
8. Cleanup: `graphify uninstall`, `graphify hook uninstall` in projects that installed it, `uv tool uninstall graphifyy`, remove our hook entries and the query log.
UNVERIFIED: exact `hook-guard` hook JSON. Copy it from `graphify claude install --project` run in a throwaway directory.
