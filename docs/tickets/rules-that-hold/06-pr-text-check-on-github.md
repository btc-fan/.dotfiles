# 06: The PR text check is a required check on GitHub

**What to build:** Each pull request to `ai` gets a check `pr-text`. It runs the `pr-rules` gate on the PR body through `ai-check` (ticket 05). Where the repo has a verify skill, it also checks that a `run.log` names the PR head commit. A project can ask `ai-adopt` for a template `ai-checks.yml` with the jobs `check` (`make check`) and `pr-text`.

**Why:** The `pr-rules` gate denied 24 times in 7 days, but only inside a Claude or Codex session on one machine. A PR made on GitHub, by a person, or by an agent without the hook skips it (E1, Task 2, `pr-rules`: KEEP-GATE-BUT-MOVE). The `verify-pr` wall is also session-only (E1, mechanisms without a row: "a CI check that run.log names the PR head SHA cannot be skipped").

**Solution:**
- `.github/workflows/pr-text.yml` runs on `pull_request_target`, types `opened`, `edited`, `synchronize`, `reopened`. The job name is `pr-text`.
- `pull_request_target` runs the workflow and the setup code of the base branch. So a PR cannot weaken its own check. The job never checks out or runs PR code.
- The body comes from the event payload into a file. It is never put into a shell line. The PR diff and the `run.log` files at the head SHA come from `gh api` as data, with the read token.
- The verify proof check runs only when `.agents/skills/verify-*/` exists at the head SHA. It uses `hooklib.verify_runs`, the parser of the session wall.
- `ai-checks.yml` for projects: `ai-adopt --tools ci` writes it. A plain `ai-adopt` never writes it. It fetches the setup repo at a pinned commit. The URL comes from the owner config (ticket 19), with a default from the setup's own `origin`.

**Rules kept:** `pr-rules` stays a session gate for fast feedback, and gets its required check here. The `verify-pr` wall stays in the session, and gets the same check on GitHub. The `ship` gate stays; the required checks back it.

**Edge cases:**
1. A workflow on `pull_request` runs the PR's copy of the workflow, so the PR can edit the check. This is why the job uses `pull_request_target` and reads PR content only as data.
2. Forks: `pull_request_target` gets a read-only token for a fork PR. The check needs only reads, so it works.
3. A project that fetches the setup repo in CI: the URL comes from config, never from a hard-coded owner. A private setup repo needs a token: the template says so and stops with a clear message, not a silent pass.
4. Private projects and Actions minutes: the template uses `ubuntu-latest` only (macOS minutes cost 10 times more). `make check` time shows in the job log.
5. The body is edited after the check: the `edited` type runs the check again. A required check reports the newest run.
6. A project with its own CI: `ai-adopt --tools ci` never overwrites an existing workflow file with the same name. It prints the 2 job blocks for the owner to add by hand.
7. `make check` in CI fails when a tool is missing (ticket 09). So the template puts the fetched setup's `ai/bin` on PATH before `make check`.
8. A fix PR needs a test file in its diff. The diff comes from the `files` API (max 3,000 files). Over that limit, the check fails with "diff too large to read".
9. An author-sessions line `main: unknown` is refused in the session. In CI the same rule applies, with the same message.
10. Difference: the PR diff and the `run.log` files come from git, not `gh api`. The job fetches `refs/pull/<n>/head` and writes the PR files as data into a separate folder. Nothing there runs. So the 3,000-file limit of edge case 8 does not apply.
11. Difference: `ai-check pr-rules --pr-body` takes `--title` and `--base` (CI gives them), and `--dir` is the folder of PR files. The `main: unknown` line now fails with no session too.
12. Difference: the template `ai-checks.yml` runs on `pull_request`, not `pull_request_target`, because the job `check` must run PR code. A PR can edit it. A `shortcut:` comment says when to split it.
13. Difference: ticket 19 is not built. The setup URL comes from `AI_SETUP_URL` (env or `~/.config/ai/config.env`), else the `origin` of the setup. `ci` is an opt-in of `ai-adopt` itself, not a `routing.yaml` rule.
14. Difference: the workflow runs on PRs to `ai` and `ai-fable`, the same branches as `tests.yml`.

**Owner steps:** None. The ruleset of ticket 04 already names `pr-text`.

**Blocked by:** 04, 05

**Status:** ready-for-agent

**Size:** M

- [ ] A PR to `ai` with a body that has no Mermaid block shows `pr-text` red, with the missing field in the log.
- [ ] After the body is fixed and saved, `pr-text` turns green with no new push.
- [x] A PR that edits `pr-text.yml` still gets the base branch version of the check (a test reads the workflow trigger).
- [ ] A PR whose verify `run.log` names an older commit shows `pr-text` red.
- [x] `ai-adopt --tools ci` on a fixture writes `.github/workflows/ai-checks.yml`. A plain `ai-adopt` writes no workflow.
- [x] The workflow passes no PR text into a `run:` line (a test greps for `github.event.pull_request.body` in `run:`).

**Verify:**
- Unit: `ai/tests/test_commands.py` gets `t_pr_text_workflow_shape` and `t_ai_checks_template`; `ai/tests/test_tier1.py` gets `t_adopt_tools_ci`.
- Drive: `$H drive cli --fixture python-with-tests ai-adopt --tools ci`, then `ai-check pr-rules --pr-body` on a good and a bad body. Gate change: a real Claude session drive of `gh pr create` with a bad body, and a Codex payload drive.
- Behaviour scenario: `gate-pr-rules` and `gate-ship` of ticket 02 pass.

**Rollback:** Delete `pr-text.yml` and the template. The owner removes `pr-text` from the ruleset.
