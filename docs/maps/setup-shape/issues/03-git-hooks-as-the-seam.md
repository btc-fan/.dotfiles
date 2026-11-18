# 03: Can git hooks carry the git rules for each agent and each repo

Type: research
Status: resolved
Blocked by: none

## Question

Can one global git hook folder enforce the owner's git rules for Claude, Codex, subagents, the shell and the
owner, in each repo, and still run the hooks that a repo already has?

Facts to find, each with a primary source (git documentation, husky, lefthook and pre-commit documentation, the
Codex and Claude Code sandbox documentation):

1. How a global `core.hooksPath` behaves when a repo sets its own `core.hooksPath` (husky) or has files in
   `.git/hooks` (the pre-commit tool). Which one wins, and how a global hook can call the repo's hook.
2. Linked worktrees: which hook folder a worktree uses.
3. Which hooks exist for the rules: commit on a protected branch, push to a protected branch, secrets in the
   staged diff and in the pushed range, `git add -A` (is there any hook point for it), commit message rules.
4. What `--no-verify` and `git -c core.hooksPath=` skip, and what still holds then (a server-side rule, the
   existing no-verify gate).
5. Does a git hook run inside the Codex sandbox and the Claude Code sandbox, with the same PATH.
6. What the known tools do for this (the pre-commit tool's `init-templatedir`, husky's design, lefthook's
   global config), in 5 lines each.

Answer shape: a table rule by rule (hook point, holds for whom, how it can be skipped), then a recommendation:
git hooks for all git rules, for some, or stay with the agent hooks.

Read first: report sections 5 and 11.

## Answer

Resolved on 2026-11-18 by a research subagent. Full findings with sources: branch `research/git-hooks-seam`,
file `docs/research/git-hooks-seam.md` (never merged).

Git hooks can carry some git rules, and a global `core.hooksPath` alone cannot do it.

- A repo-local `core.hooksPath` (husky) wins over the global value without a message. With a global value set,
  `.git/hooks` is ignored, and `pre-commit install` and `lefthook install` refuse to run.
- The research names config hooks of git 2.54 or later (`hook.<name>.command`) as the way to run a global hook
  before the repo's own hooks. This was not tested: the local git is 2.50.1.
- Rules with a hook point: commit on a protected branch (`pre-commit`, `pre-merge-commit`), push to a protected
  branch (`pre-push`), secrets in the staged diff and in the pushed range, commit message rules (`commit-msg`).
- Rules with no hook point: `git add -A`, and `--no-verify` itself. These stay with the agent hooks.
- Each git hook can be skipped with `--no-verify` or with `git -c core.hooksPath=`. A fast-forward merge and a
  cherry-pick do not run `pre-commit`. Only a server-side rule holds against a skip.

Not verified: git 2.54 config hooks, a hook run inside the Claude Code and the Codex sandbox, husky and lefthook
behaviour on a real install, rebase and amend.

Follow-up question for the map: test git config hooks on a machine with git 2.54 or later, then decide which
rules move.
