# Spec: verify evidence in git

Status: agreed with the owner on 2026-11-19 (grilling round 1). Implemented on this branch; rollout waits for the next big rollout. Branch `verify-evidence-in-git`.

## Problem Statement

The verify tool (`verify-<app>`) writes its proof to `.verify/evidence/<run>/`. The generator tells each project to put `.verify/` in `.gitignore`. So the proof stays on the machine that ran it.

The owner works on one machine. The agents often work on other machines. The owner cannot see their proof without an SSH login. A PR says "evidence in `.verify/evidence/...`", but that path does not exist on GitHub.

Measured on 2026-11-19 in two adopted projects: 21 MB in 24 runs (PNG, YAML, logs), and 4.6 MB in 34 runs (mostly `.body` response files). So one run is about 0.2 MB to 1 MB.

## Solution

Evidence goes into git with the feature branch. It shows in the PR diff on GitHub and lands in main with the squash merge. A periodic cleanup PR removes old runs from main.

Owner decisions (2026-11-19):

1. Storage: main, through the PR. No orphan branch.
2. Content: the full run folder. `.verify/data/` (app data, DB files) and DB dumps stay local.
3. Cleanup: an agent PR that removes runs older than 7 days. The owner merges it.
4. Rollout: all projects and all machines at once.

## Changes

### 1. Generator text (`ai/lib/pstack_additions/create-verification-skill.md`, then the adapter rebuilds `ai/skills/create-verification-skill/SKILL.md`)

- Replace "Add `.verify/` to the repo `.gitignore`" with: "`ai-adopt` ignores `.verify/` except `.verify/evidence/`. Commit each run folder with the change it proves."
- Add: "Never write secrets, tokens, cookies or DB dumps into the run folder. Mask them before you save a response body."
- The run folder name is `<branch>_<feature>_<DD-MM-YYYY>_<HH-MM-SS>` (UTC, EU date order; owner 2026-11-19). The feature part is left out when it is the same as the branch. A `/` in the branch becomes `-`.
- Add: "Each run writes `summary.md`: the feature, the steps, PASS or FAIL for each step, and the evidence file names." The owner reads this file first on GitHub.
- `maintain-verification-skill` additions: same rule.

### 2. `.gitignore` (`ai-adopt`, managed block)

- The managed block gets `.verify/*`, `!.verify/evidence/` and `.verify/evidence/**/.DS_Store`.
- `ai-adopt` removes a bare `.verify/` line outside the block. Reason: git cannot re-include a file when its parent folder is ignored. This is the only edit outside the block, and the adopt report names it.

### 3. Hooks (`hooklib.py`, `ai-precommit`)

The run log keeps `commit: <sha>` of the code that was driven. A commit that adds only evidence moves HEAD. The hooks must skip such commits.

- New helper `code_head(root, ref)`: the newest commit at or before `ref` that changes a path outside `.verify/evidence/`.
- Hook 4 (`pr_verify_log`): compare the run commit with `code_head(head)`, not with the PR head.
- Hook 3 (`ai-precommit`, `verify-commit`): compare with the commit time of `code_head(HEAD)`, not HEAD.
- Hooks 1 and 2 already skip `.verify/`. No change.
- `PR_GENERATED` gets `(^|/)\.verify/evidence/`, so evidence lines do not count for the 400-line PR limit.

### 4. Cleanup (7 days)

- New script `ai/bin/ai-evidence-prune <repo>`: on a new branch `chore-prune-evidence-<date>`, it runs `git rm -r` on each run folder older than 7 days (by the `finished` line, else the folder name time). It keeps the newest valid run of each feature, so main never loses its last proof.
- Trigger: the `merge-review` session-start rule (main moved since the last review). The agent runs the script and opens a PR. No push to main. The owner merges.
- Limit: `git rm` removes files from the tree, not from history. Each run stays in history (about 1 MB). The owner accepted this.

### 5. Ship skill and PR rules

- The ship skill and the PR Evidence section link to the run folder on GitHub: `https://github.com/<owner>/<repo>/tree/<branch>/.verify/evidence/<run>`.
- The ship skill checks that the run folder of the PR is committed and pushed.

### 6. Docs and tests

- Update `ai/rules/verification-skill.md` (the line "The log is gitignored and local; it never enters a commit" changes) and the hooks README.
- Tests in `test_flow.py`: `code_head` skips an evidence-only commit, so hooks 3 and 4 pass.
- Tests in `test_tier1.py`: the adopt `.gitignore` migration.
- A test for `ai-evidence-prune`: the 7-day cut, and the newest run of each feature is kept.

## Rollout (later, in one big rollout with other changes)

Owner 2026-11-19: merge the dotfiles PR, but do not roll out yet. More changes come first, then one rollout.

1. Dotfiles PR on branch `verify-evidence-in-git` (base `ai`). The owner merges. No machine or project changes.
2. Later, at the big rollout: `setup-rollout` on each machine (`ai-sync`, then `ai-doctor`).
3. `ai-adopt` on each project with a verify skill, this repo included (`verify-ai-setup`). Each project gets one PR with the new `.gitignore` and its recent evidence, after a secret scan.
4. Check from another machine: open one project PR on GitHub and read one `summary.md`.

Rollback: revert the dotfiles PR and run `ai-adopt` again. The `.gitignore` goes back to `.verify/`. Committed evidence stays in history.

## Out of Scope

- Git LFS, an orphan evidence branch, or GitHub artifacts.
- History rewrite to free space.

## Open Questions

1. Existing local evidence (up to 21 MB in one project): commit it all in the rollout PR, or only the runs of the last 7 days? Default: the last 7 days.
2. A size limit for one file (a video): default 10 MB, `ai-precommit` refuses a bigger file under `.verify/evidence/`.
