# How to run the evals

`ai/bin/ai-eval` runs the evals. It reads only the JSON case files in `ai/evals/cases/`. The `.md` files in
`ai/evals/` are manual prompt lists (format: tool | FIRE (EN ; RO ; RU) | NOT (a ; b) | signal). A person runs
them by hand, and ai-doctor counts them. Write a JSON case file when ai-eval can see the signal (a skill, a tool
call or a router rule). Use a manual list only when it cannot.

## Case files
One case is one JSON file. The file name is `<id>.json`.

```json
{
  "id": "diagnosing-bugs-ro",
  "fixture": "app",
  "prompt": "Aplicația e lentă când rulez python3 -m app.cli 2 3. Află de ce.",
  "expect": {"skills": ["diagnosing-bugs"], "rules": ["diagnosing-bugs"]}
}
```

- `fixture`: the repo where the run starts: `empty-git`, `docs-only`, `no-git`, `app` or `project-copy` (see `ai-eval --help`).
- A should-fire case uses one or more of these `expect` keys:
  - `skills`: skill names. Seen when the agent calls the Skill tool, reads `skills/<name>/SKILL.md`, or the router logs the skill.
  - `tools`: regexes. Each regex must match one tool call, written as `Name {input json}`. Example: `graphify (query|affected)`.
  - `rules`: routing rule ids that the router logs in `fired.jsonl` of the run.
- A should-not-fire case uses only these keys: `not_skills`, `not_rules`, `not_tools`. They have the same forms. One seen item makes the run a miss.
- A run is a hit when it sees every expected item and no `not_*` item.
- Names: `<tool>.json` is the English fire case, `<tool>-ro.json` and `<tool>-ru.json` are the Romanian and Russian fire cases, `<tool>-not.json` is the should-not-fire case. `ai/tests/test_eval.py` checks the keys and these names.

## Run
1. Check the plan first. No agent starts: `ai/bin/ai-eval behaviour --dry`.
2. Run: `ai/bin/ai-eval behaviour [--agent claude|codex|both] [--runs N] [--out DIR]`. Default: both agents, 3 runs per case.
3. Each run is a fresh headless session on a fresh copy of the adopted fixture: `claude -p "<prompt>" --output-format stream-json --verbose --max-turns 15` (never `--bare`), or `codex exec --json "<prompt>"`. The router state of a run goes to a folder of that run, not to your stats.
4. Read the table on stdout and `behaviour.json` in the output folder. A run that fails before any tool call (usage limit, login, crash) is an error. An error is not in the score.
5. Install level (no agent session): `ai/bin/ai-eval install`.
6. Other method for a plugin pack: `claude plugin eval` (runs with and without the plugin, grader `tool_used: Skill`).

## Scenarios
A scenario is many steps on one repo copy: `ai/evals/scenarios/<id>.json`. Run one with `ai/bin/ai-eval scenario --only <id> [--agent claude|codex|both] [--runs N]`. `--dry` lists the runs.

- Steps: `session` (a headless session, scored like a case; `max_turns` sets the turns), `git` (harness git commands with the repo hooks; add `-c core.hooksPath=/dev/null` before the subcommand to skip them), `write` (harness files inside the repo) and `check` (a state check).
- `expect` in a scenario session also takes `says`: regexes on the raw transcript, for a refusal text that no rule logs.
- `"agents"` limits a scenario to these agents.
- `"plugin": "checkout"` tests this checkout, not the installed setup. Claude loads this checkout's ai-core with `--plugin-dir` (the installed ai-core is off). Codex gets a temp `CODEX_HOME` with this checkout's hooks. The pre-commit hook runs this checkout's `ai-precommit`. A fake `gh` logs to `gh.log` of the run. `"skills"` copies skills from `ai/skills/` into the repo when the installed copy is older. `"allow"` adds Claude allowed tools.
- Checks with `"plugin": "checkout"`: `hook` runs this checkout's router on the end state with the turn start of the last session (a fresh state, so no loop limit counts) and compares the decision; `git_out` matches a git command's output; `gh_log` matches the fake gh log.
- `verify-enforcement` (Claude) and `verify-commit-gate` (Codex) prove the 4 verify hooks. Report: `docs/reports/ai-eval-verify-enforcement-2026-11-18.md`.

## Pass bars
- Should-fire: 3 of 3 runs per case.
- Should-not-fire: 0 false fires.
- Hard cases (`hard-*.json`): some misses are expected without the routing rows (estimate 10 to 25%, not measured for this setup).
- Run the evals again on every model change, and when a tool release changes its rules text or its triggers.
- Before a run, use `/context` once. If a skill shows only its name in the list, expect misses unless its routing row is on.
