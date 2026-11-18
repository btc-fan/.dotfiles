# Dev worktree never syncs the live machine

Every worktree of the dotfiles repo shares the git hooks post-merge and post-rewrite. Hook v2 and `ai-sync` sync only from the installed copy `~/.dotfiles-ai` (or a root-owned admin copy). A merge or rebase in a dev worktree changes no skill link and no Codex copy (ticket 19, R-010).

## Sub-features

- `hook-v2`: the hook runs `ai-sync` only when the worktree is `~/.dotfiles-ai`. `ai-sync --install-hook` replaces a v1 hook.
- `sync-guard`: `ai-sync` from another checkout prints one line, changes nothing and exits 0. `--dry-run` and `--check` still work there.
- `installed-sync`: a merge in the installed copy still links the skills and refreshes the Codex block.

## How to get to it (user POV)

- An agent or the owner runs `git merge`, `git rebase` or `git commit --amend` in a dev worktree such as `~/work/dotfiles-ai-verify`.
- The owner runs `git -C ~/.dotfiles-ai pull`: the hook syncs the machine.

## Driving it with verify

Preconditions: a run with `dotfiles-worktrees`, `doctor: PASS`. The kind makes the installed copy `<tmp>/home-sync/.dotfiles-ai` (branch `ai`, a copy of this checkout's `ai/`) and the dev worktree `<tmp>/dotfiles-worktrees` (branch `main`). Their shared hooks come from this checkout's `ai-sync --install-hook`. Each worktree has one branch to merge.

- **Dev merge.** `$H drive merge dev`. Expect `hook: # ai-sync-hook v2`, `rc: 0`, `HOME changed: no`.
- **Installed merge.** `$H drive merge installed`. Expect `HOME changed: yes` and links such as `.claude/skills/ship -> <tmp>/home-sync/.dotfiles-ai/ai/skills/ship`.
- **Session.** `$H drive session claude --fixture dotfiles-worktrees 'This is a throwaway test fixture repo ... (1) git switch -c feat2 && ... git commit -m feat2 (2) git switch main && git merge --no-ff feat2 -m "merge feat2" (3) readlink ~/.claude/skills/ship.'`. The session uses the real HOME. Expect the merge in the tool results and `readlink` still `~/.dotfiles-ai/ai/skills/ship`. `$H cleanup` then says `real files changed: none` (the guards include the link targets of `~/.claude/skills` and `~/.agents/skills`).

## Gotchas

- `drive merge` runs a real `git merge` with HOME=`<tmp>/home-sync`. Run each target once per run: a second merge of the same branch is "Already up to date" and runs no hook.
- The session drive uses the real HOME, so it proves the real machine stays the same. Drive `merge dev` first: if it says `HOME changed: yes`, do not drive the session.

## Proof paths

- success: `drive merge installed` gives `HOME changed: yes`.
- cancel: n/a (git runs the hook; no prompt).
- error: `drive merge dev` gives `HOME changed: no`. Before ticket 19 it listed the dev worktree links (seen on 2026-11-18: ship, release, setup-rollout, promote-skill).
- empty: n/a.
- persistence: `$H cleanup` reports `real files changed: none`.
- Unreachable: post-rewrite (a rebase) is not driven. It runs the same hook text as post-merge.
