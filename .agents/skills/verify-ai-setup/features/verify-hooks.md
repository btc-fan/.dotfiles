# Verify hooks

Planned: tickets 02 to 05 of `docs/tickets/verify-enforcement/`. The 4 hooks read `.verify/evidence/<run>/run.log` of the checkout: the tool must exist, the tool must be used, a commit that adds tests needs fresh proof, a PR needs proof of its final tree.

## Sub-features

- `vh-exists` (ticket 02): Stop and SubagentStop block a turn that edited app code in a project without a verify skill.
- `vh-used` (ticket 03): Stop and SubagentStop block a turn with an app-code change and no newer valid run.log.
- `vh-commit` (ticket 04): ai-precommit refuses a commit that adds a test without a valid run.log newer than HEAD.
- `vh-pr` (ticket 05): `gh pr create`, `gh pr edit`, `gh pr ready` need a valid run.log at the PR head.

## How to get to it (user POV)

- An agent ends a turn, commits, or opens a PR in a project.

## Driving it with verify

Preconditions: the hooks exist (they do not yet). Fixtures: `python-with-tests` (no verify skill) and a copy with a `.agents/skills/verify-app/` skill.

- **Exists.** Edit `app/calc.py` in `python-with-tests`, then `$H drive hook Stop '{"session_id":"v1"}'`: expect `decision: block` (ticket 02).
- **Commit.** Stage a new `tests/test_more.py` and run `$H drive cli --fixture python-with-tests ai-precommit`: expect a non-zero `rc` (ticket 04).
- **PR gate (ticket 05).** In `python-with-tests`: add `.agents/skills/verify-calc/SKILL.md` and `.verify/` to `.gitignore`, commit on `main` (local only: the merge-approval gate denies a push to main), then `git switch -c feat` and commit a change to `app/calc.py`. Write `.verify/evidence/r-old/run.log` with `commit:` = `main`. Drive `$H drive hook --fixture python-with-tests PreToolUse '{"session_id":"v5","tool_name":"Bash","tool_input":{"command":"gh pr ready 3"}}'` and the same for `gh pr create --title t --body-file <full body>` and `gh pr edit 3 --title y`: `decision: deny`, reason `verify proof: the PR changes app code (app/calc.py) ...`. Add `r-head/run.log` with `commit:` = `HEAD` and a `finished:` after the commit: create and edit `decision: allow`; ready is allowed after a `PostToolUse` Skill `ship` payload in the same session.
- **PR gate in Claude.** `$H drive session claude --fixture python-with-tests "This is a throwaway test repo with a fake gh. ... Run exactly this shell command once with the Bash tool: gh pr create --title 'feat: calc order' --body-file .verify/body.md ..."`: without the head log, `gates in output: pr-rules` and the stream has `verify proof:`; with it, `gates in output: none` (the drive's permission layer then stops `gh`, so `gh.log` stays empty).
- **Nudge per agent (ticket 06).** In the same fixture (with the verify skill), `$H drive session claude --fixture python-with-tests "This is a throwaway test repo. ... Step 1: with the Edit tool, add a comment line to app/calc.py. Step 2: use the Agent tool ... to add a comment line to app/cli.py ..."`: `NN-session-state/fired.jsonl` has 2 `verify-before-done` rows in one session (main agent and subagent), and both replies quote `[ai router: verify-before-done]`.
- Write the rest when the tickets land, with their own payloads.

## Gotchas

- Until tickets 02 to 05 merge, every drive above passes. That is the expected state, not a proof.

## Proof paths

- success, cancel, error, empty, persistence: n/a until tickets 02 to 05 land.
- Unreachable: all paths. Blocked by: the hooks do not exist on this branch. Route tried: none.
