# 19: a dotfiles dev worktree never changes the live machine

**What to build:** git hooks that run in a dotfiles dev worktree (post-merge, post-checkout and others that call ai-sync) never relink `~/.claude/skills`, `~/.agents/skills` or refresh the Codex plugin cache from that worktree. Only the installed copy `~/.dotfiles-ai` syncs the machine. Seen 2026-11-18: a `git merge` in `~/work/dotfiles-ai-verify` pointed live skill links (ship, release, setup-rollout, promote-skill) and the Codex plugin cache at unmerged branch code. The setup-rollout runbook already says a dev checkout may only dry-run. Cause: the shared post-merge and post-rewrite hooks (installed by `ai-sync --install-hook`) run `$(git rev-parse --show-toplevel)/ai/bin/ai-sync`, so they run the ai-sync of whichever worktree merged or rebased.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Red: a merge in a second worktree of a fixture dotfiles repo changes no link and no cache under a temp HOME.
- [x] Green: the same merge in the installed copy still syncs.
- [x] `ai-check-detect --dir /nonexistent` prints one error line and exits 2, no traceback (found by verify-ai-setup).
