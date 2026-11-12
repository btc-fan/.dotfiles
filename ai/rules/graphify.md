# graphify

Pin: PyPI `graphifyy` 0.9.105. Source: https://github.com/Graphify-Labs/graphify
Opt-in per project (owner decision 2026-11-12). Benefit on small box projects is unproven.

## Vendor rules (verbatim, AGENTS.md variant)
The verbatim block is the file `ai/rules/vendor/graphify-0.9.105-always-on-agents-md.md` (byte copy from the audited intake copy).
Deviation rule: delete the `/graphify` line on an agent where the graphify skill is not installed. Whether the intake copy equals 0.9.105: UNVERIFIED.
README at v0.9.105 (verbatim): "A code-only corpus requires no API key: `graphify extract` runs fully offline. On a mixed repo, add `--code-only` to index just the code and skip the docs/PDFs/images that would otherwise need an LLM." / "set `GRAPHIFY_BACKEND=none` to disable all LLM backends (semantic extraction and the `claude -p` labeling fallback) and keep a code-only graph." / "`graphify hook install`: auto-rebuild on commit + branch checkout (run `graphify update .` after `git pull`)".

## When / when not
- Turn it on for a big or unfamiliar codebase where "what calls what" questions are frequent. Leave it off for small projects: the Map plus rg is enough.
- On: `ai-adopt --tools graph`. It adds `graph` to `.ai/enabled`, runs `GRAPHIFY_BACKEND=none graphify extract . --code-only` (local, no key, nothing leaves the machine) and gitignores `graphify-out/`. Off: remove `graph` from `.ai/enabled`, delete `graphify-out/`.
- Where it is on: `graphify query "<question>"`, `graphify path "<A>" "<B>"`, `graphify explain "<concept>"` before broad searches. Then read only the located lines.
- Never bare `graphify .` (the skill form; headless it asks for an LLM key and fails). No semantic pass, no Graphify Cloud, no `ingest`. Never `graphify claude install` or `graphify agents install` in a project.

## Knowledge home, freshness, maintenance
- Home: `<repo>/graphify-out/` (generated, gitignored).
- Fresh: `graph.json` newer than the last code commit; the session start line says "graph stale" where it is on.
- Maintain: `graphify update .` after code changes and after `git pull`. No git hook by default (owner decision); optional owner step: `graphify hook install` (remove with `graphify hook uninstall`).

## Enforcement
- L1: opt-in routing row `graph` (session start line) only in projects that enabled it. `knowledge-check` after a commit says `graphify update .` there.
- The old global rows `no-graph`, `graph-first` and `graph-update` were removed (logs showed them ignored).
- Advisory only. Never `--strict`. `GRAPHIFY_HOOK_STRICT=0`.
- L7: `~/.cache/graphify-queries.log`.

## Proof
- Should fire (EN, enabled project): "where is the price drop alert computed?". First exploring call is `graphify query`.
- Should fire (RO, enabled project): "unde se calculeaza istoricul de pret in proiectul asta?"
- Should fire (RU, enabled project): "где считается история цен в этом проекте?"
- Should not fire: the same prompts in a project without `graph` in `.ai/enabled` (expect the Map, then rg).
- Signal: a new line in `~/.cache/graphify-queries.log`.

## Setup checklist
1. Install (per machine): `uv tool install graphifyy==0.9.105`.
2. Env (agent env and `~/.config/ai/env`): `GRAPHIFY_BACKEND=none`, `GRAPHIFY_HOOK_STRICT=0`. The build command also sets `GRAPHIFY_BACKEND=none` inline.
3. No optional extras (`mcp`, `watch`, `video`, cloud). Telemetry: none documented.
4. Per project: `ai-adopt --tools graph`.
5. Verify: `graphify --version` prints 0.9.105. In an enabled project with no LLM key set, `GRAPHIFY_BACKEND=none graphify extract . --code-only` prints a node count.
6. Cleanup: `graphify hook uninstall` where installed, `uv tool uninstall graphifyy`, delete `graphify-out/` and the query log.
