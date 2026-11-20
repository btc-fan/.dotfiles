---
name: ship
description: 'Use when a feature or fix branch is done and about to go to the owner ("ship it", "ready for review", "finish the PR", "gata", "готово"). Runs the pre-merge pipeline: make check, verify-<app>, Matt code-review, security review, the UI checklist when UI changed, then updates the PR Evidence, runs gh pr ready and asks the owner to merge. Not for a release (use the release skill).'
---

# Ship: the pre-merge pipeline

Run every step in order on the feature branch. A red step stops the pipeline: fix it, then start again at step 1.
Do not merge. The owner merges, or tells you "merge" (the merge-approval gate checks it).

## Steps

1. **Branch.** `git status` is clean, the branch is not main or master, and it is pushed. When `git remote` prints
   nothing, stop here and tell the owner "no remote": a push and a PR are not possible yet.
2. **Checks.** `make check` (the full suite, the ratchet, the Markdown placement check). Keep the command and the
   tail of its output for Evidence.
3. **Proof in the real app.** If the repo has a `verify-<app>` skill: run it on each changed feature, and make sure
   an e2e test covers the proven journey. Commit each run folder (`.verify/evidence/<run>/`, its `summary.md`
   first) and push it, so the owner reads the proof on GitHub from any machine.
4. **Review.** Run Matt's code-review skill against `git diff main...HEAD` (Standards and Spec axes, fresh
   context). Fix every finding, or write in the PR why it stays.
5. **Security.** Run `/security-review` on the branch. When the lockfile changed, also run the project's dependency
   audit (`pip-audit`, `npm audit` or `osv-scanner scan -r .`, whichever is installed). HIGH or CRITICAL: fix it.
6. **UI (only when UI files changed).** Read `design-system/<app>/MASTER.md` and the page override, then run the
   ui-ux-pro-max pre-delivery checklist (`references/pro-rules.md`) on the changed screens. For a web page with
   SEO or blog tools on in this repo: `claude-seo` page audit, or the `claude-blog` check for a post.
7. **Docs.** The Map paths still exist, a new module is in the Map, a one-way-door change has an ADR. Read each
   changed document once as STE (ASD-STE100, rules below) and rewrite each sentence that breaks a rule. A rewrite
   is a new commit: start again at step 1.
8. **PR.** Update the body (pr template): Summary with the Mermaid diagram, Evidence (Before and After, the step 2
   output tail, the step 3 evidence as a GitHub link
   `https://github.com/<owner>/<repo>/tree/<branch>/.verify/evidence/<run>` and the e2e test), Merge Danger
   (Door, Blast Radius), Docs, Changed guards.
   Read the body once as STE and rewrite each sentence that breaks a rule. Then `gh pr ready <n>`.
9. **Ask.** Tell the owner in 3 lines: what changed, the evidence, the merge danger. End with: "Say merge and I
   merge it, or approve and merge on GitHub."

## STE rules (steps 7 and 8)

Done when each sentence passes: an instruction has 20 words or fewer, a description 25 or fewer. One instruction
per sentence, in the active voice. Each word has one meaning, and the words are literal (no idioms). Code,
commands, paths and quoted output stay as they are.

## After the owner says merge

`gh pr merge <n> --squash --delete-branch`, then `git switch main && git pull --prune`. Remove the branch's worktree
(`git worktree remove <path>`) and any local branch that is left (`git branch -D <branch>`). Then run
`/improve-codebase-architecture`, then `/retro`. Their findings become tickets or a PR. Then run
`git rev-parse main > .ai/last-review`.
When the repo has committed verify evidence, run `ai-evidence-prune` on a branch `chore-prune-evidence-<date>` and open a PR.
