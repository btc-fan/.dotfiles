# 04: Winner gate for overlapping skills

**What to build:** when an agent calls a skill that loses in the overlap table (for example the OMC tdd next to Matt's tdd), the call is denied and the message names the winner. OMC and OMX win orchestration. A typed /name of the owner runs. Claude and Codex.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The overlap table is data that the router reads; the skills guide shows the same table
- [ ] Router cases: loser denied, winner passes, orchestration skills pass, typed call passes
- [ ] Works in a subagent (hook input with agent_id)
