# 04: Hook 3, the commit gate

**What to build:** `ai-precommit` refuses a commit that adds a test function or a test spec when the project has a verify skill and no valid tool log is newer than HEAD's commit time. It works for every writer: Claude, Codex, subagents, the shell, humans.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Red: staged new test, no fresh valid log: commit refused, with the command to run.
- [ ] Green: a fresh valid log: commit passes.
- [ ] Edits and deletions of existing tests pass. A project without a verify skill passes (hook 1 covers it).
- [ ] Python (`def test_`) and JS or TS (`test(`, `it(`) specs are detected.
- [ ] Works in a linked worktree.
