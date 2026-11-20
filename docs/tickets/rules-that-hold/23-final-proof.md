# 23: The whole branch is proven, and the numbers are compared with the baseline

**What to build:** One report that proves the branch `rules-that-hold` works before the owner tries it. It has the full suite, a verify sweep of each feature file, and each scenario of ticket 02 on Claude and Codex. It shows the numbers of `ai-doctor --numbers` next to the baseline. It also covers a trial adopt of one real project in a scratch copy, and a list of what is still not proven.

**Why:** The README table "Numbers that the final ticket must show" sets the targets. Reminders: 27 to 0, plus 1 status line. Global words: 3,460 to under 600. Fixed cost: about 22,790 tokens to under 11,000. Hook processes per Bash call: 7 to 3 or fewer. Router lines: 6,038 to under 3,000. Gate scenarios: 12 of 12. Files per rule change: 9.5 to 3 or fewer. Local-name lines: 124 to 0. Spec principle P6: keep only what changes the result.

**Solution:**
- `bash ai/tests/run.sh` on macOS and Linux, and the CI run of ticket 04 on the branch head.
- A verify sweep: `$H launch` with each fixture kind, then each feature file in `.agents/skills/verify-ai-setup/features/` in the order of its `README.md`.
- `ai-eval scenario` for each ticket 02 scenario, 3 runs, on Claude and Codex.
- `ai-doctor --numbers --json` on the branch, compared with `docs/reports/baseline-<date>.md`, in one table.
- A trial adopt: copy one real project into a scratch folder with no remote, run `ai-adopt`, `make check` and one Claude session there. No push.
- A full trial on a new repo (the owner asked for it on 2026-11-20). Make a new folder and a new GitHub repo. Adopt it with this branch. Send the rulesets with `ai-github-wall`. Then one agent does 5 real tasks there, each through a branch and a pull request: a feature, a bug fix with a test, a refactor, a docs change, and one task that tries a forbidden step.
- The 5 tasks follow the owner's own flow from the rules of the `ai` branch, with the owner's tools: the Map first, graphify and Serena for navigation, context7 for library docs, a worktree and a branch, the spec and ticket skills for the feature, a failing test first for the bug fix, the project's verify skill with evidence, the ship skill, then a pull request with the full PR text.
- The report has one quality table for each task: tests added, check results, review findings, tokens, turns, and each place where the agent left the flow.
- For each task the report says which rule acted, in which layer, and if the agent corrected itself. A rule that did not hold is a finding, with its ticket.
- The report `docs/reports/rules-that-hold-final-<date>.md` holds all of it, plus "Not proven".

**Rules kept:** No rule changes. The report proves that each of the 12 gates holds. It proves that each of the 27 reminders has the home that the README rule map names.

**Edge cases:**
1. Codex usage limits: a run with no tool call is an error, not a pass. The report gives the Codex count of passes, fails and errors apart. A gate with only errors on Codex goes to "Not proven".
2. Flaky scenarios: a gate needs 3 of 3. A flaky gate is a fail in this report. The ticket opens a fix ticket; it does not hide the result.
3. A number that got worse: the report marks it red and names the ticket that changed it. The owner decides, before the branch goes further.
4. A number that cannot be measured on this machine (for example Codex start text): "not measured", with the reason, never a guess.
5. The real project copy holds owner data: the scratch copy is outside the repo, it is never committed, and the report names the project as "a project".
6. The verify sweep changes a real file: the helper guard hashes catch it, and `$H cleanup` exits 1. That is a fail of this ticket.
7. The CI run and the local run disagree: both logs go into the report, and the difference is a blocker.
8. A second machine was not tried: the report says so under "Not proven".

**Owner steps:** M5: try the branch on one project with the 2 commands of the owner guide (ticket 22), after this report.

**Blocked by:** 01 to 22

**Status:** ready-for-agent

**Size:** M

- [ ] `bash ai/tests/run.sh` passes, and the CI check `tests` is green on the branch head.
- [ ] Each feature file of the verify skill has a drive in one evidence folder, and `$H evidence` says the `run.log` is proof.
- [ ] The scenario table shows each gate on Claude, and each Codex gate, with 3 runs.
- [ ] The numbers table has 9 rows: baseline, branch and target, with each target met or marked red.
- [ ] The trial adopt log shows `ai-adopt`, `make check` and one session, with no push.
- [ ] The new trial repo shows 5 pull requests with green checks, and GitHub refused 1 direct push to its default branch.
- [ ] The report names, for each of the 5 tasks, the rule that acted and its layer.
- [ ] The report has a "Not proven" list.

**Verify:**
- Unit: the full suite, `bash ai/tests/run.sh`.
- Drive: the full sweep of `.agents/skills/verify-ai-setup/features/`, with real session drives on Claude and Codex payload drives for each gate.
- Behaviour scenario: every scenario of ticket 02.

**Rollback:** Nothing to undo. The ticket writes one report. A failed number sends the work back to the ticket that owns it.
