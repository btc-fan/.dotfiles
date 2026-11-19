# 01: One command brings a machine to the newest setup

**What to build:** the owner runs `ai-update` on any machine. It pulls branch `ai` into `~/.dotfiles-ai` (fast-forward only), renders the rules, and runs `install.sh --yes` with the saved profile and the found agents. The global layer (rules, hooks, skills, plugins) is then current for every project on that machine, with no step in the projects.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Prior art: the deleted local branch `ai-catalog` had an `ai/bin/ai-update` (commit 6baf5af, 2026-11-14) with these rules, worth keeping: refuse root; refuse a dirty `~/.dotfiles-ai` and print the 3 ways out (status, stash, commit); `--no-pull` and `--dry-run`; a Linux user without admin rights gets the admin command printed instead of a run. Its catalog step is not wanted (SPEC-LOG: no per-tool YAML registry).

- [ ] `ai-update` on a machine one commit behind: pull, render, install, then `ai-doctor --quick` 0 fail, and one line: old commit, new commit.
- [ ] A dirty `~/.dotfiles-ai`: nothing changes, the 3 ways out are printed.
- [ ] `ai-update --dry-run` changes nothing.
- [ ] README "Update" names this one command.
