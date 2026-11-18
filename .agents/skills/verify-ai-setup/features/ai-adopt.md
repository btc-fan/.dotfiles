# ai-adopt

`ai-adopt` (a link to `ai-start`) adds the AI project layer to a repo: AGENTS.md blocks, CLAUDE.md, `.ai/`, `.gitignore` lines, the check targets, and a commit on the branch `ai-adopt`, pushed to origin.

## Sub-features

- `adopt-kind`: one run per fixture kind ends `rc: 0`.
- `adopt-branch`: the commit goes to the branch `ai-adopt`, never to `main`; it is pushed to origin.
- `adopt-owner-text`: a project's own `## Done` and rules stay word for word.
- `adopt-rerun`: a second run changes nothing.
- `adopt-owner-guard`: a repo whose origin owner is not in `AI_GITHUB_OWNERS` is refused.

## How to get to it (user POV)

- The owner or an agent runs `ai-adopt` in a repo (the setup-rollout skill does it per project).

## Driving it with verify

Preconditions: a run with the kinds to adopt, `doctor: PASS`.

- **Adopt each kind.** Run `$H drive cli --fixture <kind> ai-adopt --yes --no-onboard` for `empty`, `docs-only`, `python-with-tests`, `web-app`, `existing-project-with-own-Done`. Expect `ai-adopt: committed on the branch ai-adopt, not on main` and `rc: 0`; the transcript ends with `* [new branch] HEAD -> ai-adopt` to `remotes/fixture-owner/<kind>.git`.
- **Owner text.** In `existing-project-with-own-Done`, read `AGENTS.md` before cleanup: `## Done`, `- The owner saw it on staging.` and `## Rules` are still there.
- **Rerun.** Run the same command again on the same fixture. Expect `ai-adopt: nothing to change (base v4)`.
- **Dry run.** `$H drive cli --fixture <kind> ai-adopt --yes --no-onboard --dry-run` on a fresh fixture: `git status --short after` is empty.
- **Owner guard.** `$H drive cli --fixture <kind> AI_GITHUB_OWNERS=someone-else ai-adopt --yes --no-onboard`: `ai-adopt: refused, the origin remote is not one of the owner's repos`, `rc: 1`.

## Gotchas

- `--no-onboard` is required: the onboard step starts a headless claude session (ai-eval does the same).
- The remote path must be `.../<owner>/<repo>.git`. The driver sets `AI_GITHUB_OWNERS=fixture-owner`; another owner is refused.
- `python3 -m pytest` is missing on this Mac, so ai-adopt leaves the pytest target out of check-fast and says so.
- The managed `AI:verify` line under a project's own Done (ticket 06) is not there yet: the own-Done fixture gets no verify line.
- ai-adopt starts a background graphify rebuild in the temp HOME. Cleanup stops it.

## Proof paths

- success: all 5 kinds `rc: 0`, branch `ai-adopt` on the remote.
- cancel: `--dry-run`: no file changes.
- error: the owner guard refusal, `rc: 1`.
- empty: the `empty` kind adopts with `rc: 0`.
- persistence: the rerun prints `nothing to change`; the remote keeps the `ai-adopt` branch.
- Unreachable: the PR that ai-adopt opens. Blocked by the fake gh (it answers `[]` and opens nothing). Route tried: `<tmp>/gh.log` stays empty in a `--yes` run.
