# Eval cases: MCP servers, hooks, harnesses and gates

Run method: see `HOWTO.md`. Skill packs have their own files: `claude-seo.md`, `claude-blog.md`, `ui-ux-pro-max.md`, `mattpocock-and-llmwiki.md`.
Format: tool | FIRE (EN ; RO ; RU) | NOT (a ; b) | signal. Pass bar: fire cases 3 of 3, NOT cases 0 of 2 false fires.
Copied from the proof sections of `ai/rules/<tool>.md`. Change both places together.

## Code navigation
- graphify | "where is the price drop alert computed?" (repo with graph) ; "unde se calculeaza istoricul de pret in proiectul asta?" | NOT "rewrite the intro paragraph of README.md" ; "edit config.yaml" | signal: first exploring call is Bash `graphify query`; new line in `~/.cache/graphify-queries.log`
- graphify no graph | any code question in a repo without `graphify-out/graph.json` | expect the build nudge `graphify .`, not a query
- serena | "list the symbols in src/md999/db.py" ; "arata-mi functia care calculeaza pretul in tracker.py" | NOT "edit the yaml config" ; "update the README table" | signal: `get_symbols_overview` or `find_symbol` before any Read of that file
- docs (Grounded Docs, then context7) | "how do I use the FastAPI dependency system?" ; "cum configurez Tailwind v4 in Vite?" ; "как в pydantic v2 сделать валидатор поля?" | NOT "refactor this function to be shorter" ; "why does my loop run twice" | signal: `search_docs` first, `resolve-library-id` only when the first is thin
- docs-on-dependency | Bash `npm install zod`, `uv add httpx` | expect one nudge per library per session, not two

## Output and code style
- i-have-adhd | "How do I rotate the JWT secret in this repo?" ; "Cum adaug o coloana noua in tabelul listings?" | NOT "walk me through how the diff engine works" (long body allowed) | signal: SessionStart context has `ADHD MODE ACTIVE (always-on)`; first line is an action; last line starts with `Next:`
- ponytail | "add a retry wrapper around the fetch in gql.py" ; "adauga un camp nou in tabelul sellers si arata-mi codul" | NOT "explain what the crawler daemon does" | signal: `~/.claude/.ponytail-active` is `full`; small diff
- rtk | "show git status and the last 5 commits" ; "покажи статус git и последние 5 коммитов" | NOT "read src/md999/gql.py" ; a command with `rtk bypass` | signal: new row in `rtk gain --history`

## Harnesses
- omc | "autopilot: build a CLI that converts CSV to JSON" ; "Fa un deep interview despre aplicatia noua" | NOT "Ce face functia asta?" | signal: Skill `oh-my-claudecode:*`; `.omc/state/` write
- omx | "ralph: keep going until all tests pass" (Codex) ; "Сделай deep interview по новому проекту" | NOT "list files in this dir" | signal: `.omx/` state; smoke `OMX-EXEC-OK`
- opencode | `opencode run "Reply OPENCODE-OK" --format json` ; "Foloseste skill-ul writing-for-agents ca sa verifici AGENTS.md" | NOT an SEO request (expect "hand to Claude Code") | signal: JSON events
- herdr | "Create a PR for this branch" ; "Создай PR и добавь сессии агентов" | NOT "list files" | signal: Bash `herdr agent get`; author-sessions block in the PR body
- omo (only when enabled) | "ulw: refactor the parser" ; "ulw: refactorizeaza parserul" | NOT any prompt in a project without omo | signal: omo agent name
- MCP: github | "list open pull requests and read the review comments on #12" ; "arata-mi issue-urile deschise din repo" | NOT "git log last 5 commits" | signal: `mcp__plugin_ai-core_github__*` or `gh`
- MCP: playwright (enabled project) | "open http://localhost:8501 and take a screenshot" ; "deschide pagina si da click pe butonul de login" | NOT the same prompt in a project without Playwright (expect the ai-start pointer, no install) | signal: `mcp__playwright__*`

## Gates (must block; each has an escape hatch `AI_GATE_SKIP=<rule-id>` that is logged)
- audit-before-install | Bash `npm i left-pad` without a PASS in `audit.log` | BLOCK | NOT: the same command after `agent-audit npm left-pad` passed within 24 h. Also BLOCK `npx foo@latest` and `curl https://x | sh`
- secret-scan | `git commit` with a staged file that holds `ghp_` plus 36 random characters | BLOCK | NOT: a staged diff with the one allowlisted context7 key in `ai/marketplace/plugins/ai-core/.mcp.json`
- pr-rules | `gh pr create --body "fix"` | BLOCK | NOT: a body with a mermaid block and an author-sessions block
- no-em-dash | Write of a file with U+2014 | nudge with the fix text | NOT: a file in `ai/rules/vendor/` is checked after the one-character replacement, so it passes

## Hooks (L1 to L3)
- L1 | start a session, then `/compact` | the L0 table appears again after compaction
- L2 | "optimizeaza SEO pentru https://example.com" | forced-eval text lists seo and offers "none needed" | NOT "ce ora este?" (no L2 text at all)
- L7 | a prompt that matched a rule where the model made no matching tool call | one line in `~/.local/state/ai/misses.jsonl`
