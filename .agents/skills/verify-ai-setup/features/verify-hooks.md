# Verify hooks

The verify hooks make an agent build and use the project's `verify-<app>` tool. They read `.verify/evidence/<run>/run.log` of the agent's own checkout. A run counts when its log has all 4 lines (`commit`, `doctor`, `db_writes`, `finished`), `doctor: PASS` and `db_writes: no`. Hooks 1 and 2 are router walls on Stop and SubagentStop in an adopted repo. Hook 3 is a step of `ai-precommit`. Hook 4 (the PR gate, ticket 05) is planned.

## Sub-features

- `vh-exists` (ticket 02, wall `verify-tool-exists`): a turn that changed app code ends only when the project has a verify skill with one valid run.
- `vh-used` (ticket 03, wall `verify-tool-used`): a turn that changed app code ends only when a valid run finished after the first change.
- `vh-commit` (ticket 04, wall `verify-commit`): a commit that adds a test needs a valid run that finished after HEAD's commit time.
- `vh-pr` (ticket 05): planned.

## How to get to it (user POV)

- An agent or a subagent changes app code (an Edit, a shell write, a commit) and ends its turn.
- Anyone runs `git commit` with a new test function or spec in a project with a verify skill.

## Driving it with verify

Preconditions: `python-with-tests`, `doctor: PASS`. Adopt it first: `$H drive cli --fixture python-with-tests ai-adopt --yes --no-onboard` (the hooks act only where `.ai/enabled` exists). Write shell changes with `python3 -c "open(...).write(...)"`: the session allow list has `Bash(python3 *)`, not `sed` or `printf`.

- **Exists, payload.** Write `app/calc.py` by shell, then `$H drive hook Stop '{"session_id":"p1","stop_hook_active":false}'`: `decision: block`, `rules fired: verify-tool-exists`. The same with `SubagentStop` and `"agent_id":"sub1"`. Restore the file, Stop again: `decision: allow`.
- **Exists, session.** `$H drive session claude --fixture python-with-tests "<throwaway repo; run one python3 -c write of app/calc.py; if a stop hook blocks, quote it and end the turn again>"`: `rules fired` has `verify-tool-exists`; the stream has two `Stop hook feedback` blocks, then the loop limit lets the turn end.
- **Fixture setup for hooks 2 and 3.** In the fixture: add `.agents/skills/verify-app/` (a SKILL.md with Launch, Doctor, Drive, Cleanup code blocks and a `verify` helper that writes `run.log`), add `.verify/` to `.gitignore`, commit on `ai-adopt`, push `ai-adopt`, then `git -C <remote> symbolic-ref HEAD refs/heads/ai-adopt` and `git remote set-head origin ai-adopt`. A Claude subagent with `isolation: "worktree"` starts its worktree from `origin/HEAD`, so the default branch must carry the adoption and the skill.
- **Used, red (the ScripTube regression).** A session prompt that calls the Agent tool with `isolation: "worktree"` and lets the subagent write `tests/test_more.py` by `python3 -c`: `rules fired: verify-tool-used`, two walls whose `repo` is `<fixture>/.claude/worktrees/agent-<id>`.
- **Used, green.** The same prompt, and the subagent then runs the skill's launch, doctor, drive and cleanup in its worktree: no `verify-tool-*` in `rules fired`, a valid `run.log` in the worktree's `.verify/evidence/`.
- **Commit, red and green.** Pin the fixture hook: `.git/hooks/pre-commit` runs `<checkout>/ai/bin/ai-precommit` by its absolute path. Make a setup commit so HEAD is newer than every run. Then a session prompt: write `tests/test_x.py` by `python3 -c`, `git add`, `git commit`; on a refusal, run the commands it names, then commit again. Expect the refusal text `ai-precommit: blocked the commit: it adds tests`, a `verify-commit` wall, the verify steps, and a second commit that passes (`git log`).
- **PR gate (ticket 05).** In `python-with-tests`: add `.agents/skills/verify-calc/SKILL.md` and `.verify/` to `.gitignore`, commit on `main` (local only: the merge-approval gate denies a push to main), then `git switch -c feat` and commit a change to `app/calc.py`. Write `.verify/evidence/r-old/run.log` with `commit:` = `main`. Drive `$H drive hook --fixture python-with-tests PreToolUse '{"session_id":"v5","tool_name":"Bash","tool_input":{"command":"gh pr ready 3"}}'` and the same for `gh pr create --title t --body-file <full body>` and `gh pr edit 3 --title y`: `decision: deny`, reason `verify proof: the PR changes app code (app/calc.py) ...`. Add `r-head/run.log` with `commit:` = `HEAD` and a `finished:` after the commit: create and edit `decision: allow`; ready is allowed after a `PostToolUse` Skill `ship` payload in the same session.
- **PR gate in Claude.** `$H drive session claude --fixture python-with-tests "This is a throwaway test repo with a fake gh. ... Run exactly this shell command once with the Bash tool: gh pr create --title 'feat: calc order' --body-file .verify/body.md ..."`: without the head log, `gates in output: pr-rules` and the stream has `verify proof:`; with it, `gates in output: none` (the drive's permission layer then stops `gh`, so `gh.log` stays empty).
- **Nudge per agent (ticket 06).** In the same fixture (with the verify skill), `$H drive session claude --fixture python-with-tests "This is a throwaway test repo. ... Step 1: with the Edit tool, add a comment line to app/calc.py. Step 2: use the Agent tool ... to add a comment line to app/cli.py ..."`: `NN-session-state/fired.jsonl` has 2 `verify-before-done` rows in one session (main agent and subagent), and both replies quote `[ai router: verify-before-done]`.

## Gotchas

- A Claude session shell reads the owner's profile, so `~/.local/bin` comes first on PATH and the ai-adopt hook finds the installed `ai-precommit`, not this checkout's. Pin the hook as above, else the drive tests the installed copy.
- A run that finished after HEAD's commit time is proof for the next commit. A Stop block often makes the agent run the tool after a commit, so the next commit passes. For a red commit, commit something first.
- The owner's git config has `diff.mnemonicPrefix`. `ai-precommit` passes explicit `a/` and `b/` prefixes; a parser that reads `+++ b/` without them sees no file.
- `merge-approval` denies a push to the fixture's `main`. Use the `ai-adopt` branch as the fixture default branch instead.
- `bash ai/tests/run.sh` runs the verify helper on this checkout (`t_verify_ai_setup_run`) and replaces `.verify/current`. Do not run the suite while a run is live.

## Proof paths

- success: the green session (worktree subagent with a valid run) and the second commit.
- cancel: n/a (the agent cannot cancel a Stop block; the loop limit ends it after 2 blocks per tree).
- error: the red payloads and sessions; an invalid run (`doctor: FAIL`, `db_writes: yes`) is named in the message (`ai/tests/cases/verify-tool-used.json`).
- empty: no app-code change, or a docs-only change: `decision: allow`.
- persistence: the walls in the session state `walls.jsonl` and the commit in `git log`.
- Unreachable: a Codex subagent stop (Codex `codex exec` starts no subagent in this fixture). Blocked by: no subagent tool in a headless Codex run. Route tried: none; Codex Stop is covered by `ai/tests/cases/verify-tool-exists.json` (agent codex).
