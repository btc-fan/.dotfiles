# 02: Decide the place of oh-my-claudecode on the dev-mac profile

**What to build:** an owner decision, with numbers, on oh-my-claudecode (OMC) for the dev-mac profile: on in every project (today), or on per project as on the servers. Then the setup follows the decision.

Measured in a real session on 2026-11-18 (OMC 5.8.5):

- OMC loads about 84 skills, 19 agents and 30 hook commands on 11 events. The GUIDE still says 35 skills.
- The skill list is over its budget (1 percent of the context window). 12 or more skills show a name and no description.
- OMC adds a line to each Bash call ("Use parallel execution ...") and to each failed tool call.
- OMC project memory told the agent that a docs-only repo is "C/C++" (it saw a Makefile). The owner rule is: knowledge lives in the repo only.
- The winner gate already refuses the main OMC skills (plan, execute, review, tdd, research, pr, release, wiki).

**Blocked by:** None (can start immediately)

**Status:** needs-triage (the owner decided "OMC on everywhere on macOS"; this ticket asks to look at that decision again)

- [ ] A table: tokens at session start with OMC and without OMC, and the OMC skills used in the last 30 days (`ai-doctor` has the counts).
- [ ] The owner decides: every project, per project, or off.
- [ ] If OMC stays on: its project memory injection and its per-call hint lines are off, or the owner accepts them.
- [ ] After the change, each skill in the list of a new session shows its description.
