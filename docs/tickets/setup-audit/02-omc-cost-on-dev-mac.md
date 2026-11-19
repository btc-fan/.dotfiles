# 02: Decide the place of oh-my-claudecode on the dev-mac profile

**What to build:** an owner decision, with numbers, on oh-my-claudecode (OMC) for the dev-mac profile: on in every project (today), or on per project as on the servers. Then the setup follows the decision.

Measured in a real session on 2026-11-18 (OMC 5.8.5):

- OMC loads about 84 skills, 19 agents and 30 hook commands on 11 events. The GUIDE still says 35 skills.
- The skill list is over its budget (1 percent of the context window). 12 or more skills show a name and no description.
- OMC adds a line to each Bash call ("Use parallel execution ...") and to each failed tool call.
- OMC project memory told the agent that a docs-only repo is "C/C++" (it saw a Makefile). The owner rule is: knowledge lives in the repo only.
- The winner gate already refuses the main OMC skills (plan, execute, review, tdd, research, pr, release, wiki).

Added by the deep audit (report `docs/reports/setup-deep-audit-2026-11-18.md`, section 6):

- OMC starts 4 of the 7 hook processes of a Bash call, 5 of 7 at a Stop and 5 of 12 at a session start.
- It has 3 walls of its own: a Read deny for files over 1,500 lines or 45 KB after one warning, a Stop block
  when the final answer asks an option question, and a Stop block at 94 percent context.
- It appends each Bash command of the agent to `~/.bash_history`.
- It injects the nearest `AGENTS.md` again after a Read or an Edit.
- Switches that exist: `OMC_SKIP_HOOKS` (tokens `pre-tool-use`, `post-tool-use`, `post-tool-use-failure`,
  `skill-injector`, `project-memory-posttool`, `workflow-drift-guard`), `OMC_QUIET=2`, `OMC_READ_BUDGET=off`,
  `OMC_GIT_GUARDRAILS=0`, `bashHistory: false`. No switch stops the process starts or the memory injection.
- The decision itself is the map ticket `docs/maps/setup-shape/issues/02-plugins-on-dev-mac.md`.

**Blocked by:** None (can start immediately)

**Status:** needs-triage (the owner decided "OMC on everywhere on macOS"; this ticket asks to look at that decision again)

- [ ] A table: tokens at session start with OMC and without OMC, and the OMC skills used in the last 30 days (`ai-doctor` has the counts).
- [ ] The owner decides: every project, per project, or off.
- [ ] If OMC stays on: its project memory injection and its per-call hint lines are off, or the owner accepts them.
- [ ] After the change, each skill in the list of a new session shows its description.
