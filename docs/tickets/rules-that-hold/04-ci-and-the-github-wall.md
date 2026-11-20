# 04: The tests run on each pull request, and GitHub refuses a direct push

**What to build:** Each pull request to `ai` shows a check `tests` that runs the suite on macOS and on Ubuntu. A small command `ai-github-wall` prints the ruleset of the README (`--dry-run`) and sends it (`--apply`). It also reads if secret push protection is on. After the owner runs it, GitHub refuses a direct push and a merge with a red check.

**Why:** 16 of 16 large projects in the research enforce with CI (spec, section 3). This repo has no `.github/` folder and no branch protection. 30 pull requests merged in 4 days, with 18 regression ledger lines. Before R-018, a merged gate was off for a day and each local check passed. The older ticket `docs/tickets/setup-audit/05-ci-for-the-ai-branch.md` asks for the same workflow. This ticket covers it.

**Solution:**
- `.github/workflows/tests.yml` on `pull_request` to `ai`. Two jobs `tests-macos` and `tests-ubuntu` run `bash ai/tests/run.sh`. A last job named `tests` needs both. The required check name is `tests`.
- Each action is pinned by its commit SHA. `permissions: contents: read`. No secret. `timeout-minutes: 40`. A new push cancels the older run.
- The tests that need a logged-in agent are left out by an env key that the suite reads. The suite prints their names, and the job summary lists them.
- `ai/bin/ai-github-wall`: `--dry-run` prints the README JSON for the repo of the cwd. `--apply` sends it with `gh api`. `--check` prints the push protection state.
- `--apply` is idempotent: when a ruleset with the same name exists, it updates that one.

**Rules kept:** `merge-approval`, `worktree-first` and `no-verify` stay session gates; the ruleset adds a wall outside the agent. `secret-scan` stays a session gate; push protection adds the GitHub side. "Never push to main or master" (E1 row 137, MOVE-TO-CHECK) gets its check here.

**Edge cases:**
1. The owner's token has admin rights. `bypass_actors` is empty, but an admin can edit or delete the ruleset. The `--apply` output says this in one line, and the owner guide (ticket 22) repeats it.
2. A private repo on a free plan has no rulesets. `ai-github-wall` reads the error of `gh api` (403 or 404 with an upgrade message). It prints "rulesets need a public repo or a paid plan", and exits 1.
3. A matrix job reports `tests (ubuntu-latest)`, not `tests`. So the ticket uses 2 named jobs and 1 summary job. A test reads the workflow file and asserts the job name `tests`.
4. Conflict with the README JSON: the default branch `main` of this repo holds other files and has no workflow. A required check `tests` on `main` never reports, so each PR to `main` waits forever. The ticket sends 2 rulesets: the README one for `ai`, and one for the default branch with only `deletion`, `non_fast_forward` and `pull_request`.
5. The suite takes about 20 minutes (outline figure, not measured here). The ticket measures one run and writes the time into the workflow comment.
6. Ubuntu picks the `server` profile by default. The router suite passes `--profile` (ticket 03), and `tests-ubuntu` sets `AI_PROFILE=dev-mac` for the other tests.
7. The `gh-write` gate asks before `gh api` with a write. So the agent never runs `--apply`. It prints the command for the owner (step M2).
8. A pull request can change `tests.yml` itself. With 0 required reviews, the owner reads each workflow change. The PR template line "Changed guards" names it.
9. Hooks use `/usr/bin/python3`. Both runners have it. The job prints its version (macOS 3.9 is the low bound).

**Owner steps:**
- M1: `ai-github-wall --dry-run` (prints the JSON it would send).
- M2: `ai-github-wall --apply` (it calls `gh api repos/<owner>/<repo>/rulesets`).
- M3: `gh api repos/<owner>/<repo> --jq .security_and_analysis` (secret push protection must say `enabled`).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Size:** M

- [ ] A pull request to `ai` shows the check `tests`, green on both operating systems.
- [ ] A pull request with a broken test shows `tests` red.
- [ ] The job summary lists each test that was left out because it needs a logged-in agent.
- [ ] Each `uses:` line in the workflow names a 40-character commit SHA (a test reads the file).
- [ ] `ai-github-wall --dry-run` prints valid JSON with `"bypass_actors": []` and changes nothing on GitHub.
- [ ] After M2, `git push origin ai` from a local branch is refused by GitHub (owner evidence).

**Verify:**
- Unit: `ai/tests/test_commands.py` gets `t_github_wall_dry_run` (a fake `gh` on PATH) and `t_tests_workflow_shape` (job names, pinned SHAs, no secret).
- Drive: `$H drive cli ai-github-wall --dry-run` and `--apply` against the fake `gh`. The evidence shows the logged `gh api` call.
- Behaviour scenario: `gate-merge-approval` and `gate-worktree-first` of ticket 02 must still pass.

**Rollback:** Delete the workflow file and `ai-github-wall`. The owner deletes the rulesets in the GitHub settings.
