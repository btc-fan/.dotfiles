# Verify enforcement scenario: the 4 hooks end to end (2026-11-18)

Ticket: `docs/tickets/verify-enforcement/done/07-scenario.md`. Spec: `docs/specs/verify-enforcement.md`.

## Commands

```
ai/bin/ai-eval scenario --only verify-enforcement --agent claude --runs 3 --out <temp folder>
ai/bin/ai-eval scenario --only verify-commit-gate --agent codex --runs 3 --out <temp folder>
```

Both scenarios set `"plugin": "checkout"`. The sessions load the hooks of the checkout under test, not the installed setup:

- Claude: `--plugin-dir <checkout>/ai/marketplace/plugins/ai-core`, the installed ai-core off, `--strict-mcp-config`, the env of `ai/adapters/env.list`.
- Codex: a temp `CODEX_HOME` with the checkout's `codex-hooks.json`.
- The fixture pre-commit hook runs the checkout's `ai-precommit` by its absolute path. A session shell reads the user profile, so `ai-precommit` on `PATH` is the installed copy.
- The installed `create-verification-skill` is still typed-only. The scenario copies the checkout's model-invocable copy into the fixture (`"skills"`), git-excluded.
- A fake `gh` logs to `gh.log` of the run.

Fixture: `app` (adopted by `ai-adopt`), with its `verify-app` skill removed, on branch `feat`.

## Results (3 runs each)

| Hook | Red (the hook blocks) | Green (the hook allows after a real verify run) | Claude | Codex |
|---|---|---|---|---|
| 1 tool exists (Stop) | wall `verify-tool-exists` after one shell write of `app/calc.py` | the agent runs `create-verification-skill`, builds `.agents/skills/verify-app/`, proves it once; replay `Stop` = allow | 3/3 | n/a |
| 2 tool used (SubagentStop, linked worktree) | wall `verify-tool-used`, repo `<fixture>/.claude/worktrees/agent-<id>` | the subagent runs the tool in its worktree; replay `SubagentStop` in that worktree = allow | 3/3 | n/a |
| 3 commit gate (git pre-commit) | `ai-precommit: blocked the commit: it adds tests`, wall `verify-commit` | the agent runs launch, doctor, drive, cleanup; the same commit passes; `tests/test_gate.py` is in HEAD | 3/3 | 3/3 |
| 4 PR gate (`gh pr create`) | deny `verify proof: the PR changes app code (app/calc.py, app/version.py) ...` | the agent runs the tool at the PR head; the retry reaches the fake gh (`gh.log`); replay `PreToolUse` = allow | 3/3 | n/a |
| Run passes | | | 3/3 | 3/3 |

Flake rate: 0 of 3 for every check, for both agents.

Each verify wall fired exactly once per run. The loop limit is 2 blocks per app-code state. So in every run the hook itself let the turn end after the proof; the loop limit did not.

Session times (Claude, runs 1 to 3): hook 1 116 s, 77 s, 101 s (15 to 20 turns); hook 2 35 s, 28 s, 55 s; hook 3 16 to 19 s; hook 4 13 to 15 s.

## How green is measured

- Hooks 3 and 4: the real hook in the session. The second commit lands, and the second `gh pr create` reaches the fake gh.
- Hooks 1 and 2: the stop that ends the turn leaves no record when it allows. The check `hook` replays the checkout's router on the end state with a fresh state folder. The state has only the turn start of the last session, so the replay sees the same changed files as the live hook, and no loop counter. It must answer `allow`.

## Findings

1. An open feature prompt never made hook 1 go red. In a trial run the prompt was "add sub(a, b) and a test, do not commit". The agent read the session-start status line ("Verify skill: missing. Agent task: build verify-<app> ..."), ran `create-verification-skill` first and proved the tool before it changed code. The Stop hook had nothing to block (0 of 1 red). The status line works. The scenario now asks for one shell write first and an immediate turn end, so the hook gets a turn to block.
2. Hooks 2, 3 and 4 went red and green on the first trial run, and 3 of 3 after.
3. The `writing-for-agents` gate fired in 2 of 3 runs while the agent wrote the new `SKILL.md`. The agent loaded the skill and went on. No run failed on it.
4. Codex followed the refusal text of hook 3 in 3 of 3 runs: it ran the 4 tool steps it names, then the same commit.

## Limits

- Codex runs only the commit gate. Hooks 1 and 2 for Codex are covered by `ai/tests/cases/verify-tool-exists.json` and `verify-tool-used.json` (hook payloads). `codex exec` starts no subagent here.
- The fixture tool of the Codex scenario is a small helper that the harness writes. The Claude scenario uses the tool that the agent built in hook 1.
- One machine, one model version per agent, 3 runs. Run the scenarios again after a model change or a change to the verify hooks.

## Evidence

- Per run: `scenario.json` in the out folder, and `stream-N.jsonl` plus `state-N/` (`fired.jsonl`, `walls.jsonl`) per session under `scenarios/<agent>/<id>-<run>/`.
- Kept copy of these runs: `.verify/evidence/<run>-ve07-scenario/ai-eval/` in the checkout (gitignored, local).
- Harness tests: `ai/tests/test_eval.py` (`t_scenario_checkout`, `t_scenario_dry`).
