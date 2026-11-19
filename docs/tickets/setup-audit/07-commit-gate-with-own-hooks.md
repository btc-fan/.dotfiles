# 07: The verify commit gate also works in a repo with its own git hooks

**What to build:** verify hook 3 (a commit that adds tests needs a fresh verify run) holds in each adopted project. Today the gate is a step of `ai-precommit`. `ai-adopt` installs `ai-precommit` only when the repo has no pre-commit hook of its own and no `core.hooksPath`. A repo with husky, lefthook or the pre-commit tool keeps its hooks, and so it has no commit gate. The owner sees no warning.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Red first: a fixture repo with its own pre-commit hook accepts a commit that adds a test with no verify run.
- [ ] The gate runs in that repo too, and the repo's own hooks still run unchanged.
- [ ] `ai-adopt` prints which hook path it used. `ai-doctor` warns when an adopted project with a verify skill has no commit gate.
- [ ] A line in `docs/REGRESSIONS.md` if the owner counts this as a bug.
