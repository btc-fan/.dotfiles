# 05: The tests run on every pull request to the ai branch

**What to build:** a pull request to `ai` shows a red or green check from the test suite. Today the branch has no CI. The suite (64 test files) runs only when an agent or the owner starts it. The ledger has 9 regressions in 2 days (R-001 to R-009), and one day added about 6,800 lines.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A workflow runs the whole suite on each pull request to `ai`, on macOS and on Ubuntu.
- [ ] The run needs no secret and no logged-in agent. Tests that need a live agent stay out and are listed.
- [ ] The workflow file passes `agent-audit` (actions pinned by commit).
- [ ] A red run blocks `gh pr ready` through the ship skill, or the owner decides that it only warns.
