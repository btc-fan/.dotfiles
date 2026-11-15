
Git workflow (from the Matt Pocock skills; owner 2026-11-15)
- Feature or fix work: before the first edit, create a branch named after the feature slug. Use the same slug as docs/specs/<slug>.md and docs/tickets/<slug>/ (a fix: fix-<slug>). Never commit on main or master. A trivial change (typo, one line) also gets its own branch.
- Commit each ticket on that branch (/implement commits at the end). Move the finished ticket file to docs/tickets/<slug>/done/ in the same commit.
- After the first ticket commit: push the branch and open a draft PR (gh pr create --draft, with the full PR body). Push each later ticket to it.
- When all tickets are done and make check is green: update the PR body (Evidence), then gh pr ready. Never merge: the owner merges.
- /implement-spec: the feature branch is the integration branch, one worktree per ticket. Remove the worktrees at the end.
- prototype/<name> and research/<name> branches: push them, never merge them, never open a PR for them. Link them from the ticket.
- code-review compares against the merge-base with main (git diff main...HEAD).
- A fix commit and its PR state the cause that turned out right.
