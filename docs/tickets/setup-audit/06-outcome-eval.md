# 06: An eval that compares task results with and without the setup

**What to build:** `ai-eval` answers the question "does the setup make the agent better at the task?". Today the evals measure if a rule fired and if a skill was called. They do not measure if the task was solved, how many tokens it cost, or how long it took. No run compares a session with the setup against a session without it.

Why now:

- The evolution scenario of 2026-11-18 passed 0 of 3 runs for Claude and 0 of 3 for Codex.
- Owner goal G9: each plugin is proven useful or removed.
- Outside measurements (2026) put RTK between 0 and 8 percent more cost, and found that Serena and LSP tools are not used unless a rule nudges them. These need a check on our own tasks.
- Claude Code has `claude plugin eval`, which runs each case with a no-plugin baseline.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 5 fixed tasks on fixture repos (a bug fix, a small feature, a refactor, a library upgrade, a question about the code), each with a pass or fail check that does not read the transcript.
- [ ] 2 arms: no setup, and the full setup. Each arm runs 3 times. The report shows pass rate, tokens, cost and time per arm.
- [ ] One more arm per tool that has a cost: RTK off, Serena off, graphify off, OMC off.
- [ ] The report names each tool that does not pay for itself. The owner decides what to remove.
- [ ] The first report is kept under `docs/reports/`.
