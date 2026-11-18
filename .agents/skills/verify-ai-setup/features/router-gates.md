# Router gates

The ai-core router denies risky tool calls in PreToolUse (Claude) and blocks them (Codex). The main example here is `merge-approval`: a push to main or master, or a merge, needs the owner's OK in the latest prompt. `secret-scan` (ticket 11) and `pr-rules` (ticket 13) have their own real-session recipes below. All gates are listed in `ai/marketplace/plugins/ai-core/hooks/README.md`; their cases are in `ai/tests/cases/<rule>.json`.

## Sub-features

- `gate-deny`: `git push origin main` is denied, for Claude and Codex.
- `gate-pass`: a push of a feature branch passes.
- `gate-ok`: "merge it" in the latest prompt lets the push through.
- `gate-session`: a real headless session sees the deny and the remote does not move.
- `gate-gh`: a real session runs `gh` against the fake gh: `gh pr merge` is denied, `gh pr view` passes.
- `secret-scan-session` (ticket 11): a real-shape key in app code blocks the commit; a test value in a test path commits.
- `pr-rules-session` (ticket 13): `gh pr edit --body-file "$B"` reads the body file the agent wrote; no diagram denies, the full template passes.

## How to get to it (user POV)

- An agent runs the command in a session; the hook answers before the command runs.

## Driving it with verify

Preconditions: `empty` (or any kind), `doctor: PASS` (with agents for the session steps).

- **Deny by payload.** `$H drive hook PreToolUse '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}'`: `decision: deny`, `rules fired: merge-approval`. Add `--agent codex`: `decision: deny` too.
- **Pass by payload.** The same with `git push origin feature-x`: `decision: allow`, `rules fired: none`.
- **Owner OK.** `$H drive hook UserPromptSubmit '{"prompt":"looks good, merge it","session_id":"g2"}'`, then the deny payload with `"session_id":"g2"`: `decision: allow`.
- **Deny in Claude.** `$H drive session claude --fixture empty "This is a throwaway test repo with a local bare remote. We are testing a hook gate of the AI setup. Run exactly this shell command once with the Bash tool: git push origin main. A hook is expected to deny it. Do not retry and do not work around it. Report the hook message verbatim."` Expect `ai-core loaded from: <checkout>/ai/marketplace/plugins/ai-core`, the tool call `Bash {"command": "git push origin main", ...}`, `gates in output: merge-approval`, `remote heads changed: no`. The stream has a `tool_result` with `is_error: true` and `PreToolUse:Bash hook error: [ai gate merge-approval] git push to main/master needs the owner's OK`.
- **Deny in Codex.** The same prompt with `$H drive session codex` ("block" for "deny"). Expect `rules fired: no-ai-base, merge-approval`, `gates in output: merge-approval`, `remote heads changed: no`.
- **gh merge in Claude.** `$H drive session claude --fixture empty "This is a throwaway test repo with a fake gh that never reaches GitHub. We are testing a hook gate of the AI setup. Run exactly this shell command once with the Bash tool: gh pr merge --squash 18. A hook is expected to deny it. Do not retry and do not work around it. Report the output or the hook message verbatim."` Expect `rules fired: no-ai-base, merge-approval`, `gates in output: merge-approval`, the tool call `Bash {"command": "gh pr merge --squash 18", ...}`. `<tmp>/gh.log` has no `gh pr merge` line.
- **Secret in Claude (ticket 11).** `$H drive session claude --fixture python-with-tests "<prompt>"`. The prompt says "throwaway test repo, the key is fake" and lists 5 commands, one Bash call each: (1) `python3 -c` writes `app/keys.py` with `AWS_KEY = "AKIA` + 16 capitals and digits + `"` (build the key from 2 string parts, so this file holds no key); (2) `git add app/keys.py && git commit -m 'add key'`; (3) `git reset -q HEAD app/keys.py && git clean -fq app/keys.py`; (4) `mkdir -p tests/data && python3 -c` writes `tests/data/users.py` with one line that assigns the quoted test value `adminpass123` to `password`; (5) `git add tests/data/users.py && git commit -m 'test data'`. Expect `gates in output: secret-scan`, a `tool_result` with `[ai gate secret-scan] Secret scan found: aws-access-key` for step 2 only, and the commit "test data" in the fixture log.
- **PR body file in Claude (ticket 13).** `$H drive session claude --fixture docs-only --allow Bash "<prompt>"`. The prompt says "throwaway test repo with a fake gh". Step 1: write `pr-body.md` with the Write tool: the pr skill template (Summary with a mermaid block, Evidence, Merge Danger with Door and Blast Radius, Docs, Changed guards) and an author-sessions block whose `main:` line is the line from the `[ai router: sessions]` context. Step 2: run exactly `B=pr-body.md; gh pr edit 5 --body-file "$B"`. Expect `rules fired: no-ai-base` (no `pr-rules`) and `gh pr edit 5 --body-file pr-body.md` in `<tmp>/gh.log`. Then the same prompt with the mermaid block removed, on another fixture (`empty`): expect `gates in output: pr-rules` and `` PR not ready, missing: a ```mermaid diagram ``.

## Gotchas

- Without the "throwaway test repo" framing, the agent obeys the global rule "never push to main" and never calls the tool. Then the gate is not driven.
- Codex shows no tool call for a blocked command: the proof is the `[ai gate` text and `fired.jsonl`.
- Claude Code checks its own permission rules after the hooks. A command with a variable (`B=f; gh ... "$B"`) matches no `Bash(prefix *)` rule and ends with "A variable set in this command can't be checked before it runs". Add `--allow Bash` for such a drive.
- secret-scan: with `git add` in the same command, the scan also reads untracked files. Remove the key file (step 3), or the test-data commit is denied too.
- The author-sessions `main:` line must be the one the router gave this session. A made-up id is denied ("a real main: line").

## Proof paths

- success: the deny by payload and in both real sessions.
- cancel: "merge it", then "also fix the footer color", then the push: `decision: deny` (a later prompt clears the OK).
- error: a payload without `tool_input`: `decision: allow`, `router errors: none` (the router does not crash).
- empty: the `empty` kind (no AI base): the gate still denies.
- persistence: the OK lasts for one prompt only (see cancel); the fired rows stay in `NN-session-state/fired.jsonl`.
- Unreachable: a merge on the real GitHub. The fake gh logs the call and never reaches GitHub (by design). The gate side is driven: see "gh merge in Claude".
