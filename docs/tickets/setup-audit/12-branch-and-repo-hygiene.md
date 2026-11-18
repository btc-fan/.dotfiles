# 12: Clean the old branches and worktrees; decide on a repo for the AI setup

**What to build:** the dotfiles repo holds only branches and worktrees that are in use, and the owner decides if the AI setup moves to its own repo.

State on the main Mac on 2026-11-18:

- Local branches `verify-enforcement` and `verify-hook-last-change`: their PRs (13, 14) are merged. The owner rule says to delete them.
- Branch `ai-profiles`: one commit "wip ... not tested, do not merge", 114 commits behind `ai`.
- Branch `ai-catalog`: 4 commits ahead, 114 behind, with a worktree.
- A second worktree of the `ai` line stays on an old commit (detached, 3 PRs behind).
- The `ai` branch shares a repo with `main` (personal shell files), `windows` and `ubuntu-server`. It is 156 commits away from `main` and will never merge into it. A PR targets `ai`, while the tools and the rules call the default branch `main`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human (deletes need the owner's OK for each branch)

- [ ] The owner says keep or delete for: `ai-profiles`, `ai-catalog` and its worktree, the old worktree.
- [ ] The two merged local branches are deleted after a check that their PR state is MERGED.
- [ ] The owner decides: the AI setup stays a branch, or moves to its own repo with `main` as its default branch. A move gets its own spec (install path, the 3 machines, the pins, the open PRs).
