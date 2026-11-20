# 05: One entry point runs a gate from the hook, the git hook and CI

**What to build:** A command `ai-check <gate> --command "<cmd>" | --staged | --pr-body <file>` runs the same gate function that the agent hook runs. The agent hook, `ai-precommit` and a CI job all call that function. A person in a plain terminal gets the same answer as the agent.

**Why:** Today the gate logic lives only behind the hook. A person, a GUI git client or another tool skips it completely, and Codex hooks fail open (file D, section 2.6). E1 marks `secret-scan` and `pr-rules` KEEP-GATE-BUT-MOVE: the same check must also run in the commit hook and on GitHub. `ai-precommit` today runs linters and the verify commit gate, but no secret scan.

**Solution:**
- `ai/bin/ai-check` imports `hooklib` and calls `GATES[<id>]` with a small context for "no session". No gate logic is copied.
- First gates: `secret-scan` (`--command`, `--staged`) and `pr-rules` (`--pr-body`, plus the diff of the branch against its base).
- Also `text`: the em dash check, moved from the router into one `hooklib` function.
- Exit 0 = pass, exit 1 = fail, exit 2 = wrong usage. A failure prints the gate id, the reason, and how to fix it.
- `ai-precommit` imports the same function in-process (no new process) and runs `secret-scan` on the staged diff.
- `--dir PATH` sets the repo. Default: the cwd. The root comes from `git rev-parse --show-toplevel`.
- `ai-check --list` prints the gates it offers and, for each other gate, why it is not offered.

**Rules kept:** `secret-scan` stays a session gate, and its home grows to the commit hook. `pr-rules` stays a session gate, and gets a caller for CI (ticket 06). The em dash rule moves its function into `hooklib`; the reminder row stays until ticket 07.

**Edge cases:**
1. Gates that need session state are not offered: `merge-approval` (the owner's OK lives in the session), `writing-for-agents` and `ship` (the skill proof), `ask-first` and `gh-write` (an ask). `ai-check merge-approval` exits 2 and says why.
2. The gate functions take a router context today. The no-session context must give the same answers. One test runs each case file of `secret-scan` and `pr-rules` through the hook and through `ai-check`, and compares the decisions.
3. Python path: `ai/bin` tools use `#!/usr/bin/env python3`. A git hook in a GUI client can have a short PATH. `ai-precommit` already runs there, so `ai-check` uses the same shebang and stdlib only (3.9 works).
4. Speed: the commit hook must stay fast. Budget: under 2 s for `secret-scan --staged` on a 1,000-line diff with `gitleaks`. The test prints the time.
5. `gitleaks` is missing: the built-in patterns still run, and the output says "gitleaks not found: built-in patterns only". This is the same rule as the hook today.
6. The cwd is not a git repo, or the repo has no commit: `--staged` exits 2 with "not a git repo" or reads an empty diff and passes. It never crashes.
7. A monorepo: the root is the git top level. Paths in the reason are relative to it.
8. Codex: the hook keeps its own call. The commit hook now covers Codex sessions too, because git runs it for each agent.

**Owner steps:** None.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Size:** M

- [ ] `ai-check secret-scan --staged` refuses a staged fake key in a plain terminal, with no agent running.
- [ ] `ai-check pr-rules --pr-body body.md` refuses a body with no Mermaid block and names the missing field.
- [ ] One test sends the same input to the router hook, to `ai-precommit` and to `ai-check`, and gets the same decision from each.
- [ ] `grep` proof in the PR: the secret patterns and the PR field list exist in one module only.
- [ ] `ai-check --list` names each gate that is not offered, with the reason.

**Verify:**
- Unit: `ai/tests/cases/secret-scan.json` and `ai/tests/cases/pr-rules.json` run through `ai-check` too (a new loop in `ai/tests/test_router.py`); add `t_check_three_callers` to `ai/tests/test_flow.py`.
- Drive: `$H drive cli --fixture python-with-tests ai-check secret-scan --staged` after a staged fake key; then a real `git commit` in the fixture. Gate change: a real Claude session drive and a Codex payload drive (`$H drive hook --agent codex PreToolUse ...`) of `git commit` with the key.
- Behaviour scenario: `gate-secret-scan` and `gate-pr-rules` of ticket 02 pass on Claude and Codex.

**Rollback:** Revert. The hook keeps its own call to the gate, so nothing else breaks.
