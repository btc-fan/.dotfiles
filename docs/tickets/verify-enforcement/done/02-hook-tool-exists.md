# 02: Hook 1, the verify tool must exist

**What to build:** in a project with app code and no verify skill, a turn that edited app code cannot end (Stop and SubagentStop). The message tells the agent to build the tool with the generator and prove it once.

**Blocked by:** 01

**Status:** done

- [x] Red: a fixture repo with app code, no verify skill, and an app-code edit in the turn: the turn end is blocked, for the main agent and for a subagent.
- [x] Green: the same repo with a verify skill and one evidence run: the turn ends.
- [x] No block in a repo without app code (docs only, empty) or for a turn without an app-code edit.
- [x] Works in a linked worktree (root from the agent's cwd).
