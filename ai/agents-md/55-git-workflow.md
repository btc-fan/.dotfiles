
Git workflow (from the Matt Pocock skills; owner 2026-11-15, merge and release 2026-11-16)
- Feature or fix work: before the first edit, create a branch named after the feature slug. Use the same slug as docs/specs/<slug>.md and docs/tickets/<slug>/ (a fix: fix-<slug>). Never commit on main or master. A trivial change (typo, one line) also gets its own branch.
- Commit each ticket on that branch (/implement commits at the end). Move the finished ticket file to docs/tickets/<slug>/done/ in the same commit.
- After the first ticket commit: push the branch and open a draft PR (gh pr create --draft, with the full PR body). Push each later ticket to it.
- Feature done: run the ship skill (make check, verify-<app>, code-review, security review, UI checklist, Evidence, gh pr ready). Then ask the owner.
- Every PR goes through the owner. Merge (gh pr merge --squash --delete-branch) only after the owner's latest message says merge or approve; else the owner merges. Never push to main or master. The merge-approval gate enforces both.
- After a merge (yours, or the owner's on GitHub): delete the merged branch locally and on the remote, and its worktree (git worktree remove <path>, then git worktree prune). A squash merge hides the branch from git branch --merged: check that gh pr view <branch> --json state says MERGED, then git branch -D. Ticket branches go when their integration branch is merged. Keep main, master, prototype/ and research/ branches, and each branch without a merged PR (list those for the owner).
- After a merge to main: the session start says so (it also names local branches whose remote branch is gone). Run /improve-codebase-architecture and /retro; their findings become tickets or a PR, not direct edits on main.
- The owner says release (or tags a version): run the release skill.
- /implement-spec: the feature branch is the integration branch, one worktree per ticket. Remove the worktrees at the end.
- prototype/<name> and research/<name> branches: push them, never merge them, never open a PR for them. Link them from the ticket.
- code-review compares against the merge-base with main (git diff main...HEAD).
- A fix commit and its PR state the cause that turned out right.
