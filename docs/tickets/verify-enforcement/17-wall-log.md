# 17: every wall logs its fires, ai-doctor shows them

**What to build:** each block or refusal (gate deny, stop block, ai-adopt refusal, audit refusal, verify hooks 1 to 4) writes one log line, and `ai-doctor` shows a 7-day table per wall: fires, and the last 3 examples. After 7 days, any verify hook with more than 1 in 3 false fires becomes a hint (owner decision 2026-11-18).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] One log format for all walls: time, machine, repo, wall id, short reason.
- [ ] `ai-doctor` prints the 7-day table; the wall review in this ticket uses it.
- [x] A test writes 2 fires and reads them back in the table.

**Progress (2026-11-18):** log `walls.jsonl` (`hooklib.log_wall`): router denies and stop blocks, `stop-check.py`
blocks, ai-adopt and agent-audit refusals. `ai-doctor` prints "walls, last 7 days" (test `t_doctor_wall_table` in `ai/tests/test_skills.py`).
Open: the wall review needs 7 days of logs after the rollout. The verify hooks 1 to 4 (tickets 02 to 05) log
through the router deny path when they deny.
