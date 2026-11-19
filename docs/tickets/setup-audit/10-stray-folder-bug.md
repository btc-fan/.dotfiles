# 10: No folder named advice.detachedHead=false in a project

**What to build:** the setup never leaves an empty folder named `advice.detachedHead=false` in a project root. Found on 2026-11-18 on the main Mac in 2 places: a project adopted that day, and an old worktree of the dotfiles `ai` branch. The folder is empty and untracked. A git option (`-c advice.detachedHead=false`) was read as a path by some command. The cause is not known yet.

Narrowed on 2026-11-18: `ai-adopt` did not make the folder in 11 fixture runs. The string is used only by the
installer steps that clone a pinned tool. In `server-start` the folder was made on 2026-11-16 at 15:43, between
`ai-start` (14:14) and the adopt commit (19:10). OMC project memory lists it as a main directory of the project.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The command that makes the folder is found (use the diagnosing-bugs loop; candidates: the installer clone steps, RTK's rewrite of a `git -c` command, a worktree step).
- [ ] A test that failed before the fix.
- [ ] `ai-doctor` reports the folder in an adopted project and names the fix.
- [ ] A line in `docs/REGRESSIONS.md`.
