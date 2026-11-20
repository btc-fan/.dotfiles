
Git workflow (from the Matt Pocock skills; owner 2026-11-15, merge and release 2026-11-16)
- Every job (feature, fix, trivial change) runs in its own worktree beside the repo, made before the first edit: git worktree add ../<repo>-<slug> -b <slug> origin/<main>. The base is main or master, or the branch the owner names. The slug is the same as docs/specs/<slug>.md and docs/tickets/<slug>/ (a fix: fix-<slug>). Never commit on main or master. The worktree-first gate blocks an agent edit in an adopted repo whose checkout is on main or master.
- Commit each ticket on that branch (/implement commits at the end). Move the finished ticket file to docs/tickets/<slug>/done/ in the same commit.
- After the first ticket commit: push the branch. Open a draft PR (gh pr create --draft, with the full PR body) only when I asked for a PR, a feature or a fix in this session. Else show the branch and ask. Push each later ticket to it.
- Feature done: run the ship skill (make check, verify-<app>, code-review, security review, UI checklist, Evidence, gh pr ready). Then ask the owner.
- Every PR goes through the owner. Merge (gh pr merge --squash --delete-branch) only after the owner's latest message says merge or approve; else the owner merges. Never push to main or master. The merge-approval gate enforces both.
- After a merge (yours, or the owner's on GitHub): delete the merged branch locally and on the remote, and its worktree (git worktree remove <path>, then git worktree prune). A squash merge hides the branch from git branch --merged: check that gh pr view <branch> --json state says MERGED, then git branch -D. Ticket branches go when their integration branch is merged. Keep main, master, prototype/ and research/ branches, and each branch without a merged PR (list those for the owner).
- After a merge to main: the session start says so (it also names local branches whose remote branch is gone). Run /improve-codebase-architecture and /retro; their findings become tickets or a PR, not direct edits on main.
- The owner says release (or tags a version): run the release skill.
- /implement-spec: the feature branch is the integration branch, one worktree per ticket. Remove the worktrees at the end.
- prototype/<name> and research/<name> branches: push them, never merge them, never open a PR for them. Link them from the ticket.
- code-review compares against the merge-base with main (git diff main...HEAD).
- A fix commit and its PR state the cause that turned out right.
