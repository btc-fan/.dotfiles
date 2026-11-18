# 03: Can git hooks carry the git rules for each agent and each repo

Type: research
Status: open
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
