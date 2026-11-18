# 17: every wall logs its fires, ai-doctor shows them

**What to build:** each block or refusal (gate deny, stop block, ai-adopt refusal, audit refusal, verify hooks 1 to 4) writes one log line, and `ai-doctor` shows a 7-day table per wall: fires, and the last 3 examples. After 7 days, any verify hook with more than 1 in 3 false fires becomes a hint (owner decision 2026-11-18).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] One log format for all walls: time, machine, repo, wall id, short reason.
- [ ] `ai-doctor` prints the 7-day table; the wall review in this ticket uses it.
- [ ] A test writes 2 fires and reads them back in the table.
