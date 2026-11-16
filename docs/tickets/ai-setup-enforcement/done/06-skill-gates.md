# 06: Gates for must-use skills

**What to build:** an edit of AGENTS.md, CLAUDE.md, CLAUDE.local.md or a SKILL.md is denied until writing-for-agents is loaded or read; a bug or performance prompt cannot end the turn until diagnosing-bugs was used (once per session); gh pr ready is denied until ship ran. Claude and Codex (apply_patch included).

**Blocked by:** 05

**Status:** done except the behaviour run (it needs real headless sessions; the owner runs ai-eval behaviour)

- [x] New rule fields require_skill and strength stop
- [x] Router cases for each gate, deny and pass
- [ ] Behaviour level: each gate fires in 3 of 3 runs
- [x] ai-eval behaviour uses a max-turns cap high enough for the Stop gate to fire (was 4, now 15)
