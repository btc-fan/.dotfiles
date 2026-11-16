---
name: ship
description: 'Use when a feature or fix branch is done and about to go to the owner ("ship it", "ready for review", "finish the PR", "gata", "готово"). Runs the pre-merge pipeline: make check, verify-<app>, Matt code-review, security review, the UI checklist when UI changed, then updates the PR Evidence, runs gh pr ready and asks the owner to merge. Not for a release (use the release skill).'
---

# Ship: the pre-merge pipeline

Run every step in order on the feature branch. A red step stops the pipeline: fix it, then start again at step 1.
Do not merge. The owner merges, or tells you "merge" (the merge-approval gate checks it).

## Steps

1. **Branch.** `git status` is clean, the branch is not main or master, and it is pushed.
2. **Checks.** `make check` (the full suite, the ratchet, the Markdown placement check). Keep the command and the
   tail of its output for Evidence.
3. **Proof in the real app.** If the repo has a `verify-<app>` skill: run it on each changed feature, keep the
   evidence path, and make sure an e2e test covers the proven journey.
4. **Review.** Run Matt's code-review skill against `git diff main...HEAD` (Standards and Spec axes, fresh
   context). Fix every finding, or write in the PR why it stays.
5. **Security.** Run `/security-review` on the branch. When the lockfile changed, also run the project's dependency
   audit (`pip-audit`, `npm audit` or `osv-scanner scan -r .`, whichever is installed). HIGH or CRITICAL: fix it.
6. **UI (only when UI files changed).** Read `design-system/<app>/MASTER.md` and the page override, then run the
   ui-ux-pro-max pre-delivery checklist (`references/pro-rules.md`) on the changed screens. For a web page with
   SEO or blog tools on in this repo: `claude-seo` page audit, or the `claude-blog` check for a post.
7. **Docs.** The Map paths still exist, a new module is in the Map, a one-way-door change has an ADR.
8. **PR.** Update the body (pr template): Summary with the Mermaid diagram, Evidence (Before and After, the step 2
   output tail, the step 3 evidence path and e2e test), Merge Danger (Door, Blast Radius), Docs, Changed guards.
   Then `gh pr ready <n>`.
9. **Ask.** Tell the owner in 3 lines: what changed, the evidence, the merge danger. End with: "Say merge and I
   merge it, or approve and merge on GitHub."

## After the owner says merge

`gh pr merge <n> --squash --delete-branch`, then `git switch main && git pull`. The next session start asks for
`/improve-codebase-architecture` and `/retro` (merge-review rule).
