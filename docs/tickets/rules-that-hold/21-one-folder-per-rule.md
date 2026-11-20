# 21: A new rule is one folder, one row and one test

**What to build:** Each gate lives in `ai/checks/<id>/`: its function, its deny text and its case file. `ai/routing.yaml` is the one register. Each other copy is generated: the docs table, the gate list of the README, the golden fixture. One tool catalog lists each plugin and MCP server. `docs/EXTENDING.md` gives 4 recipes and the 3 questions. A contract test adds a throwaway rule and asserts which files changed.

**Why:** One rule change touches 9.5 files in 6 layers (median of 6 PRs; spec, section 2). One plugin id is typed in 7 files (E2, list 3, item 6: `router.py`, `ai-start`, `ai-info`, `ai-doctor`, `pins.env`, `claude.sh`). E1 found 14 mechanisms that enforce something but have no row (home-folder, `pr-url`, the verify walls, `verify-commit`, the stop check and others). The spec goal G6: a new rule needs 1 folder, 1 line to register it, and 1 test.

**Solution:**
- `ai/checks/<id>/check.py` (the gate function), `deny.md` (the text the agent sees), `cases.json` (moved from `ai/tests/cases/<id>.json`).
- The router finds a gate by its row in `ai/routing.yaml`. No other table in code lists gates (`GATES` and `GATE_PROBES` are built from the folders).
- `ai-render` generates the docs table, the README gate list and the golden fixture. `ai-render --check` fails when a tracked copy differs.
- `ai/tools.yaml` is the one catalog of plugins and MCP servers: id, marketplace, default scope, opt-in key. The 7 places read it.
- `ai/checks/_template/` holds a sample gate with 1 fire case and 1 no-fire case.
- `docs/EXTENDING.md` gives the recipes for a hard rule, a skill, a plugin or MCP server, and a project-only rule. It also asks the 3 questions of spec section 6.8.

**Rules kept:** Each of the 12 gates keeps its id, its logic and its deny text; only the file it lives in changes. Each of the 14 mechanisms without a row gets a row. Or it gets 1 line in `docs/EXTENDING.md` that names it as tool safety (for example the `ai-start` walls).

**Edge cases:**
1. The 14 mechanisms without a row: some are walls on Stop (`pr-url`, the verify walls), some are tool safety (`ai-start` refusals). The PR has a table with each one and its choice.
2. Import paths for the Codex and Hermes copies: Codex loads the plugin folder, so `ai/checks` must be inside the plugin or on its import path. The installer copies it into the plugin cache. Hermes (if ticket 18 has not moved it) uses the same path.
3. A rule that needs 2 events: `merge-approval` stores the OK on UserPromptSubmit and denies on PreToolUse. Its folder holds both handlers, and its row lists both events.
4. Backwards names in logs: `walls.jsonl` and `misses.jsonl` use the gate id. Ids do not change, so the 7-day history of `ai-doctor --numbers` still matches.
5. Counting conflict with the README target "3 or fewer files": a folder with 3 files plus 1 row touches 4 files. The contract test counts the folder as 1 place, and the PR says so.
6. Codex hook trust: the plugin content changes, so Codex asks for a new trust once. `ai-sync` runs the trust step, and `ai-doctor` reports untrusted hooks.
7. A generated copy is edited by hand: `ai-render --check` fails in `make check` and in CI (ticket 04).
8. A project-only rule must not need a core folder. The recipe sends it to the project's `make check` or `.claude/settings.json` deny rules (spec, section 6.7).

**Owner steps:** None.

**Blocked by:** 17

**Status:** ready-for-agent

**Size:** L

- [ ] Each of the 12 gates has a folder in `ai/checks/` with 3 files.
- [ ] `ai/tests/cases/` holds no gate case file.
- [ ] The contract test copies `_template` to a throwaway id, adds 1 row, and runs the suite. It finds tracked changes only in that folder and that row.
- [ ] `ai-render --check` fails when the README gate list is edited by hand.
- [ ] A plugin id appears in `ai/tools.yaml` and in no other tracked code file (grep in the PR).
- [ ] `docs/EXTENDING.md` holds the 4 recipes and the 3 questions.

**Verify:**
- Unit: `bash ai/tests/run.sh`; `ai/tests/test_commands.py` gets `t_contract_new_rule` and `t_one_tool_catalog`.
- Drive: `$H drive hook --agent claude PreToolUse` and `--agent codex` for each gate; a real Claude session drive of `git commit --no-verify`.
- Behaviour scenario: all 12 gate scenarios of ticket 02, on Claude and Codex.

**Rollback:** Revert. The change is structure, not behaviour, so the suite is the guard.
