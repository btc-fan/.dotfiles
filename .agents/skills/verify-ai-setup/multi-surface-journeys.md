# Multi-surface journeys

Flows that cross surfaces. Each one starts from a fresh `$H launch` with the named kinds and `$H doctor`.

## Adopt, then a gate in a real session

CLI, then a headless agent session, then git state.

- **Adopt.** `$H drive cli --fixture docs-only ai-adopt --yes --no-onboard`. Expect `rc: 0` and the branch `ai-adopt` on the remote.
- **Session.** `$H drive session claude --fixture docs-only "<the router-gates.md deny prompt>"`. Expect `ai-core loaded from: <checkout>/ai/marketplace/plugins/ai-core`, `gates in output: merge-approval`, `remote heads changed: no`.
- **Codex.** The same prompt with `$H drive session codex`. Same end state.
- End state: the remote has `main` (launch) and `ai-adopt` (the adopt) and nothing else.

## Install plan, then the browser tool in a project

Installer, then CLI.

- **Install plan.** `$H drive install dev-mac`: the Playwright plugin is planned and off.
- **Browser tool.** `$H drive cli --fixture web-app AI_PROFILE=dev-mac ai-adopt --tools browser --yes --no-onboard --dry-run`: the MCP install is planned.
- End state: `real files changed: none`, `git status --short after` empty.

## Subagent in a worktree, then the turn end, then a commit

Session, then git state, then the pre-commit hook. The recipes are in [features/verify-hooks.md](features/verify-hooks.md).

- **Red.** A subagent with `isolation: "worktree"` writes a test by shell and makes no run: `verify-tool-used` blocks its stop twice.
- **Green.** The same subagent runs the skill's launch, doctor, drive and cleanup: its turn ends.
- **Commit.** A new test with no run newer than HEAD: the commit is refused; after the run named in the refusal it passes.
- End state: one `verify-tool-used` wall per red stop, a valid `run.log` in the worktree, the second commit in `git log`.

## The 4 verify hooks end to end (ai-eval scenario)

Sessions, then git state, the pre-commit hook and the PR gate. `ai-eval` runs this journey, not `$H`: it has no launch or doctor. The scenarios use this checkout's plugin (`"plugin": "checkout"`), so the installed setup does not count. Report: `docs/reports/ai-eval-verify-enforcement-2026-11-18.md`.

- **Claude.** `ai/bin/ai-eval scenario --only verify-enforcement --agent claude --runs 3 --out <temp folder>`. Fixture `app` without its verify skill, on branch `feat`.
  - Hook 1: a feature prompt. Expect rule `verify-tool-exists`, skill `create-verification-skill`, then the check `hook Stop = allow`.
  - Hook 2: a subagent with `isolation: "worktree"` changes `app/calc.py` by shell. Expect rule `verify-tool-used`, then the check `hook SubagentStop = allow` in the worktree.
  - Hook 3: after an empty harness commit, a new test and `git commit`. Expect the text `blocked the commit: it adds tests`, then `tests/test_gate.py` in HEAD.
  - Hook 4: after a harness commit of app code, `gh pr create`. Expect the text `verify proof:`, then the check `hook PreToolUse = allow` and `pr create` in the fake gh log.
- **Codex.** `ai/bin/ai-eval scenario --only verify-commit-gate --agent codex --runs 3 --out <temp folder>`. The harness writes a small `verify-app` tool. Expect the same hook 3 refusal, then `tests/test_gate.py` in HEAD.
- End state: per run, `scenario.json` in the out folder, and `stream-N.jsonl` and `state-N/` per session under `scenarios/<agent>/<id>-<run>/`.

## Bug prompt, then the turn end

Hook payloads in one session: see stop-rules.md. A real session version is planned with ticket 14 (hint instead of stop).
